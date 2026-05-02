Stage 1
When I think about what a campus notification platform needs to do, the core use cases are pretty straightforward — students need to see their notifications when they log in, know which ones they haven't read yet, and be able to mark them as done. On the admin side, someone needs to be able to broadcast to all students at once.
Here's the API contract I'd propose:
MethodEndpointWhat it doesGET/api/v1/notificationsReturns all notifications for the logged-in studentGET/api/v1/notifications/unreadReturns only unread onesGET/api/v1/notifications/priority?n=10Returns top N by priorityGET/api/v1/notifications/type/{type}Filter by Placement, Result, or EventPATCH/api/v1/notifications/{id}/readMarks one notification as readPATCH/api/v1/notifications/read-allMarks everything as readPOST/api/v1/notifications/sendAdmin only — broadcast to students
Sample response for GET /api/v1/notifications:
json{
  "studentID": "1042",
  "notifications": [
    {
      "id": "d146095a-0d86-4a34-9e69-3900a14576bc",
      "type": "Placement",
      "message": "Amazon hiring drive on May 10",
      "timestamp": "2026-04-22 17:51:30",
      "isRead": false
    }
  ],
  "total": 100,
  "unreadCount": 12
}
Sample request for POST /api/v1/notifications/send:
json{
  "type": "Placement",
  "message": "Infosys hiring drive on May 15",
  "targetStudentIDs": ["all"]
}
For real-time delivery I'd go with WebSockets. When a student logs in, the browser opens a WebSocket connection. Whenever a new notification arrives, the server pushes it directly without waiting for the client to poll. The badge count updates instantly. If the connection drops, missed notifications are queued and delivered on reconnect.

Stage 2
For persistent storage I'd choose PostgreSQL. It handles complex JOIN queries well, has built-in enum support which fits notification types perfectly, and is ACID compliant so we don't lose data. For scale it works well with PgBouncer for connection pooling.
Schema:
sqlCREATE TYPE notification_type AS ENUM ('Event', 'Result', 'Placement');

CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type notification_type NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tracks which student has read which notification
CREATE TABLE student_notifications (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES students(id),
    notification_id UUID REFERENCES notifications(id),
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
Problems as data grows:
ProblemSolutionSlow reads with 5M+ rowsIndex on student_id, is_read, created_atFull table scansPartition student_notifications by student_id rangeWrite spikes on notify-allAsync job queue with Celery + RedisDB hit on every page loadRedis cache for unread counts
Fetch unread notifications:
sqlSELECT n.id, n.type, n.message, n.created_at
FROM notifications n
JOIN student_notifications sn ON n.id = sn.notification_id
WHERE sn.student_id = 1042
  AND sn.is_read = FALSE
ORDER BY n.created_at DESC;
Students who got placement notifications in last 7 days:
sqlSELECT s.id, s.name, s.email
FROM students s
JOIN student_notifications sn ON s.id = sn.student_id
JOIN notifications n ON sn.notification_id = n.id
WHERE n.type = 'Placement'
  AND n.created_at >= NOW() - INTERVAL '7 days';

Stage 3
Looking at the original query:
sqlSELECT * FROM notifications
WHERE studentID = 1042 AND isRead = false
ORDER BY createdAt DESC;
Why this is slow:
No index exists on studentID or isRead, so the database scans every row — O(n) with 5 million records. SELECT * also pulls unnecessary columns.
Should we index every column?
No. Indexes speed up reads but slow down every INSERT and UPDATE because the DB must update each index too. Disk usage also grows significantly. Only index columns used in WHERE clauses.
Targeted indexes:
sqlCREATE INDEX idx_sn_student_unread
ON student_notifications(student_id, is_read)
WHERE is_read = FALSE;

CREATE INDEX idx_notifications_created
ON notifications(created_at DESC);
Optimised query:
sqlSELECT n.id, n.type, n.message, n.created_at
FROM notifications n
JOIN student_notifications sn ON n.id = sn.notification_id
WHERE sn.student_id = 1042
  AND sn.is_read = FALSE
ORDER BY n.created_at DESC;
Cost drops from O(n) full scan to O(log n) index lookup.
Students with placement notifications in last 7 days:
sqlSELECT s.id, s.name, s.email
FROM students s
JOIN student_notifications sn ON s.id = sn.student_id
JOIN notifications n ON sn.notification_id = n.id
WHERE n.type = 'Placement'
  AND n.created_at >= NOW() - INTERVAL '7 days';

Stage 4
Problem: DB is queried on every page load for every student. At 50,000 students this doesn't scale.
Option 1 — Redis Cache (recommended)
Cache each student's unread count in Redis with a 30 second TTL. Page loads read from cache. Invalidate only when a notification arrives or gets marked read. Tradeoff: up to 30s staleness, but that's fine for a counter.
Option 2 — Polling with debounce
Client polls every 30 seconds instead of on every page load. Simple to implement, not real-time.
Option 3 — WebSocket push
Server pushes updates only when data changes. Best UX, zero wasted DB calls. Requires infrastructure to maintain 50,000 open connections.
My choice: Redis cache combined with WebSocket push. Cache solves the page load problem. WebSocket handles real-time updates when new notifications arrive.

Stage 5
Problems with original implementation:
function notify_all(student_ids, message):
    for student_id in student_ids:
        send_email(student_id, message)
        save_to_db(student_id, message)
        push_to_app(student_id, message)
Sending 50,000 emails one by one synchronously is extremely slow. If the email API fails at student 200, the remaining students don't get saved to DB either. No retry logic exists and email delivery is tightly coupled with data persistence.
Redesigned:
function notify_all(student_ids, message):
    # Step 1 — bulk insert to DB immediately
    bulk_save_to_db(student_ids, message)

    # Step 2 — queue email and push jobs async
    for student_id in student_ids:
        enqueue_email_job(student_id, message)
        enqueue_push_job(student_id, message)

    return {"status": "queued", "count": len(student_ids)}
Why DB first: Bulk insert for 50K rows completes in under a second. The notification is persisted immediately — students see it in-app even if email fails entirely.
Why async queue: Workers send emails in parallel with automatic retry on failure. Email and DB are now fully decoupled.
Should DB save and email happen together? No. DB save is the source of truth and must always succeed. Email is best-effort. Coupling them means a temporary email API failure would block all notifications from being saved.

Stage 6
Priority Inbox approach:
I score each notification using type weight combined with recency:
priority_score = type_weight * 1,000,000,000 + unix_timestamp
Type weights:

Placement → 3
Result → 2
Event → 1

Multiplying by 1 billion ensures type always dominates. The oldest Placement notification still ranks above the newest Event. Within the same type, recency decides the order via unix timestamp.
API endpoint:
GET /notifications/priority?n=10
Keeping top-N efficient as new notifications arrive:
Use a min-heap of size N. For each new notification, compute score and push to heap. If heap exceeds N, pop the minimum. This gives O(log N) per insert rather than O(n log n) full sort every time.
Implementation: See notification_app_be/app.py — get_top_n_notifications() function.