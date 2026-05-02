import requests
import sys
import os
 
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logging_middleware.logger import Log
 
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJNYXBDbGFpbXMiOnsiYXVkIjoiaHR0cDovLzIwLjI0NC41Ni4xNDQvZXZhbHVhdGlvbi1zZXJ2aWNlIiwiZW1haWwiOiJsZzUwNjRAc3JtaXN0LmVkdS5pbiIsImV4cCI6MTc3NzcwMTAwMSwiaWF0IjoxNzc3NzAwMTAxLCJpc3MiOiJBZmZvcmQgTWVkaWNhbCBUZWNobm9sb2dpZXMgUHJpdmF0ZSBMaW1pdGVkIiwianRpIjoiMzIzOGViZjgtODIxNi00MTA1LTlhZjgtODU1ODIwNmQ4ZTBiIiwibG9jYWxlIjoiZW4tSU4iLCJuYW1lIjoiZ2FuZXNoIGwiLCJzdWIiOiIwNDIyYjZhNC04ZmQ1LTRjZmUtODk0Ny00NWJmZDk3MmEzM2QifSwiZW1haWwiOiJsZzUwNjRAc3JtaXN0LmVkdS5pbiIsIm5hbWUiOiJnYW5lc2ggbCIsInJvbGxObyI6InJhMjMxMTAwMzAyMDEzNiIsImFjY2Vzc0NvZGUiOiJRa2JweEgiLCJjbGllbnRJRCI6IjA0MjJiNmE0LThmZDUtNGNmZS04OTQ3LTQ1YmZkOTcyYTMzZCIsImNsaWVudFNlY3JldCI6InFCZG5WSGZQdXB2WW1adHkifQ.vD8VgStq8SmkKIetyAFCPciJLAnCxGoHGzuv89tEpZo"
 
BASE_URL = "http://20.207.122.201/evaluation-service"
 
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}
 
 
def fetch_depots():
    """Fetch all depots with their mechanic hours."""
    Log("backend", "info", "service", "Fetching depots from evaluation service.")
    response = requests.get(f"{BASE_URL}/depots", headers=HEADERS)
    data = response.json()
    depots = data.get("depots", [])
    Log("backend", "info", "service", f"Fetched {len(depots)} depots successfully.")
    return depots
 
 
def fetch_vehicles():
    """Fetch all vehicles/tasks with duration and impact."""
    Log("backend", "info", "service", "Fetching vehicles from evaluation service.")
    response = requests.get(f"{BASE_URL}/vehicles", headers=HEADERS)
    data = response.json()
    vehicles = data.get("vehicles", [])
    Log("backend", "info", "service", f"Fetched {len(vehicles)} vehicles successfully.")
    return vehicles
 
 
def knapsack(vehicles, mechanic_hours):
    """
    0/1 Knapsack algorithm to maximise total impact score
    within the available mechanic hours budget.
 
    vehicles      : list of dicts with TaskID, Duration, Impact
    mechanic_hours: int - total available hours for this depot
    """
    n = len(vehicles)
    W = mechanic_hours
 
    # Build DP table
    dp = [[0] * (W + 1) for _ in range(n + 1)]
 
    for i in range(1, n + 1):
        duration = vehicles[i - 1]["Duration"]
        impact = vehicles[i - 1]["Impact"]
        for w in range(W + 1):
            # Don't take this vehicle
            dp[i][w] = dp[i - 1][w]
            # Take this vehicle if it fits
            if duration <= w:
                dp[i][w] = max(dp[i][w], dp[i - 1][w - duration] + impact)
 
    # Backtrack to find selected tasks
    selected = []
    w = W
    for i in range(n, 0, -1):
        if dp[i][w] != dp[i - 1][w]:
            selected.append(vehicles[i - 1])
            w -= vehicles[i - 1]["Duration"]
 
    return dp[n][W], selected
 
 
def run_scheduler():
    """Main scheduler — fetches data and runs knapsack per depot."""
    print("=" * 60)
    print("   VEHICLE MAINTENANCE SCHEDULER")
    print("=" * 60)
 
    depots = fetch_depots()
    vehicles = fetch_vehicles()
 
    if not depots or not vehicles:
        Log("backend", "error", "service", "Failed to fetch depots or vehicles.")
        print("[ERROR] Could not fetch data from server.")
        return
 
    for depot in depots:
        depot_id = depot["ID"]
        mechanic_hours = depot["MechanicHours"]
 
        print(f"\n{'─'*60}")
        print(f"  Depot ID     : {depot_id}")
        print(f"  Mechanic Hours Available: {mechanic_hours}")
        print(f"{'─'*60}")
 
        Log("backend", "info", "cron_job", f"Running scheduler for depot {depot_id} with {mechanic_hours} hours.")
 
        max_impact, selected_tasks = knapsack(vehicles, mechanic_hours)
 
        total_duration = sum(t["Duration"] for t in selected_tasks)
 
        print(f"  Max Impact Score : {max_impact}")
        print(f"  Total Hours Used : {total_duration} / {mechanic_hours}")
        print(f"  Tasks Selected   : {len(selected_tasks)}")
        print(f"\n  Selected Tasks:")
        print(f"  {'TaskID':<45} {'Duration':>10} {'Impact':>8}")
        print(f"  {'─'*45} {'─'*10} {'─'*8}")
 
        for task in selected_tasks:
            print(f"  {task['TaskID']:<45} {task['Duration']:>10} {task['Impact']:>8}")
 
        Log("backend", "info", "cron_job",
            f"Depot {depot_id} scheduled: {len(selected_tasks)} tasks, impact={max_impact}, hours_used={total_duration}.")
 
    print(f"\n{'='*60}")
    print("  Scheduling Complete!")
    print(f"{'='*60}\n")
 
 
if __name__ == "__main__":
    run_scheduler()