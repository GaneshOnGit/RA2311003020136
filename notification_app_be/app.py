from flask import Flask, jsonify, request
import requests
from datetime import datetime
import sys
import os
 
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logging_middleware.logger import Log
 
app = Flask(__name__)
 
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJNYXBDbGFpbXMiOnsiYXVkIjoiaHR0cDovLzIwLjI0NC41Ni4xNDQvZXZhbHVhdGlvbi1zZXJ2aWNlIiwiZW1haWwiOiJsZzUwNjRAc3JtaXN0LmVkdS5pbiIsImV4cCI6MTc3NzcwMTAwMSwiaWF0IjoxNzc3NzAwMTAxLCJpc3MiOiJBZmZvcmQgTWVkaWNhbCBUZWNobm9sb2dpZXMgUHJpdmF0ZSBMaW1pdGVkIiwianRpIjoiMzIzOGViZjgtODIxNi00MTA1LTlhZjgtODU1ODIwNmQ4ZTBiIiwibG9jYWxlIjoiZW4tSU4iLCJuYW1lIjoiZ2FuZXNoIGwiLCJzdWIiOiIwNDIyYjZhNC04ZmQ1LTRjZmUtODk0Ny00NWJmZDk3MmEzM2QifSwiZW1haWwiOiJsZzUwNjRAc3JtaXN0LmVkdS5pbiIsIm5hbWUiOiJnYW5lc2ggbCIsInJvbGxObyI6InJhMjMxMTAwMzAyMDEzNiIsImFjY2Vzc0NvZGUiOiJRa2JweEgiLCJjbGllbnRJRCI6IjA0MjJiNmE0LThmZDUtNGNmZS04OTQ3LTQ1YmZkOTcyYTMzZCIsImNsaWVudFNlY3JldCI6InFCZG5WSGZQdXB2WW1adHkifQ.vD8VgStq8SmkKIetyAFCPciJLAnCxGoHGzuv89tEpZo"
 
BASE_URL = "http://20.207.122.201/evaluation-service"
 
AUTH_HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}
 
# Priority weight by type (Placement > Result > Event)
TYPE_WEIGHT = {
    "Placement": 3,
    "Result": 2,
    "Event": 1
}
 
 
def fetch_notifications():
    """Fetch all notifications from the evaluation server."""
    Log("backend", "info", "service", "Fetching notifications from evaluation service.")
    try:
        response = requests.get(f"{BASE_URL}/notifications", headers=AUTH_HEADERS)
        print(f"[DEBUG] Status Code: {response.status_code}")
        print(f"[DEBUG] Raw Response: {response.text[:500]}")
        data = response.json()
        notifications = data.get("notifications", [])
        Log("backend", "info", "service", f"Fetched {len(notifications)} notifications.")
        return notifications
    except Exception as e:
        print(f"[DEBUG] Exception: {e}")
        Log("backend", "error", "service", f"Failed to fetch notifications: {str(e)}")
        return []
 
 
def compute_priority_score(notification):
    """
    Priority score = type_weight * 1000 + recency_score
    Recency: more recent = higher score
    """
    type_weight = TYPE_WEIGHT.get(notification.get("Type", "Event"), 1)
 
    try:
        ts = datetime.strptime(notification["Timestamp"], "%Y-%m-%d %H:%M:%S")
        recency_score = int(ts.timestamp())
    except Exception:
        recency_score = 0
 
    return type_weight * 1_000_000_000 + recency_score
 
 
def get_top_n_notifications(notifications, n=10):
    """Return top N notifications sorted by priority score."""
    scored = []
    for notif in notifications:
        score = compute_priority_score(notif)
        scored.append({**notif, "priorityScore": score})
 
    scored.sort(key=lambda x: x["priorityScore"], reverse=True)
    return scored[:n]
 
 
# ─────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────
 
@app.route("/", methods=["GET"])
def health():
    Log("backend", "info", "route", "Health check endpoint called.")
    return jsonify({"status": "ok", "service": "notification_app_be"}), 200
 
 
@app.route("/notifications", methods=["GET"])
def all_notifications():
    """Return all notifications from evaluation server."""
    Log("backend", "info", "route", "GET /notifications called.")
    notifications = fetch_notifications()
    return jsonify({"notifications": notifications, "count": len(notifications)}), 200
 
 
@app.route("/notifications/priority", methods=["GET"])
def priority_inbox():
    """
    Priority Inbox — returns top N notifications.
    Query param: n (default 10, max 20)
    Example: GET /notifications/priority?n=10
    """
    try:
        n = int(request.args.get("n", 10))
        n = min(max(n, 1), 20)  # clamp between 1 and 20
    except ValueError:
        n = 10
 
    Log("backend", "info", "route", f"GET /notifications/priority called with n={n}.")
 
    notifications = fetch_notifications()
 
    if not notifications:
        Log("backend", "warn", "route", "No notifications found.")
        return jsonify({"error": "No notifications available"}), 404
 
    top_n = get_top_n_notifications(notifications, n)
 
    Log("backend", "info", "route", f"Returning top {len(top_n)} priority notifications.")
 
    return jsonify({
        "top": n,
        "count": len(top_n),
        "notifications": top_n
    }), 200
 
 
@app.route("/notifications/by-type/<notification_type>", methods=["GET"])
def notifications_by_type(notification_type):
    """Filter notifications by type: Placement, Result, Event"""
    Log("backend", "info", "route", f"GET /notifications/by-type/{notification_type} called.")
 
    valid_types = ["Placement", "Result", "Event"]
    if notification_type not in valid_types:
        return jsonify({"error": f"Invalid type. Must be one of {valid_types}"}), 400
 
    notifications = fetch_notifications()
    filtered = [n for n in notifications if n.get("Type") == notification_type]
 
    return jsonify({
        "type": notification_type,
        "count": len(filtered),
        "notifications": filtered
    }), 200
 
 
if __name__ == "__main__":
    Log("backend", "info", "service", "Notification app backend starting on port 5000.")
    app.run(debug=True, port=5000)