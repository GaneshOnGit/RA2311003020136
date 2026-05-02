import requests
 
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJNYXBDbGFpbXMiOnsiYXVkIjoiaHR0cDovLzIwLjI0NC41Ni4xNDQvZXZhbHVhdGlvbi1zZXJ2aWNlIiwiZW1haWwiOiJsZzUwNjRAc3JtaXN0LmVkdS5pbiIsImV4cCI6MTc3NzcwMTAwMSwiaWF0IjoxNzc3NzAwMTAxLCJpc3MiOiJBZmZvcmQgTWVkaWNhbCBUZWNobm9sb2dpZXMgUHJpdmF0ZSBMaW1pdGVkIiwianRpIjoiMzIzOGViZjgtODIxNi00MTA1LTlhZjgtODU1ODIwNmQ4ZTBiIiwibG9jYWxlIjoiZW4tSU4iLCJuYW1lIjoiZ2FuZXNoIGwiLCJzdWIiOiIwNDIyYjZhNC04ZmQ1LTRjZmUtODk0Ny00NWJmZDk3MmEzM2QifSwiZW1haWwiOiJsZzUwNjRAc3JtaXN0LmVkdS5pbiIsIm5hbWUiOiJnYW5lc2ggbCIsInJvbGxObyI6InJhMjMxMTAwMzAyMDEzNiIsImFjY2Vzc0NvZGUiOiJRa2JweEgiLCJjbGllbnRJRCI6IjA0MjJiNmE0LThmZDUtNGNmZS04OTQ3LTQ1YmZkOTcyYTMzZCIsImNsaWVudFNlY3JldCI6InFCZG5WSGZQdXB2WW1adHkifQ.vD8VgStq8SmkKIetyAFCPciJLAnCxGoHGzuv89tEpZo"
 
LOG_API_URL = "http://20.207.122.201/evaluation-service/logs"
 
VALID_STACKS = ["backend", "frontend"]
VALID_LEVELS = ["debug", "info", "warn", "error", "fatal"]
VALID_PACKAGES_BACKEND = ["cache", "controller", "cron_job", "db", "domain",
                           "handler", "repository", "route", "service"]
VALID_PACKAGES_SHARED = ["auth", "config", "middleware", "utils"]
VALID_PACKAGES_FRONTEND = ["api", "component", "hook", "page", "state", "style"]
 
 
def Log(stack: str, level: str, package: str, message: str):
    """
    Reusable logging function that sends logs to the Afford Medical Test Server.
 
    Args:
        stack   : "backend" or "frontend"
        level   : "debug", "info", "warn", "error", "fatal"
        package : valid package name based on stack
        message : log message string
    """
 
    # Validate inputs
    if stack not in VALID_STACKS:
        print(f"[LOG ERROR] Invalid stack: '{stack}'. Must be one of {VALID_STACKS}")
        return None
 
    if level not in VALID_LEVELS:
        print(f"[LOG ERROR] Invalid level: '{level}'. Must be one of {VALID_LEVELS}")
        return None
 
    all_valid_packages = VALID_PACKAGES_BACKEND + VALID_PACKAGES_SHARED + VALID_PACKAGES_FRONTEND
    if package not in all_valid_packages:
        print(f"[LOG ERROR] Invalid package: '{package}'.")
        return None
 
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
 
    payload = {
        "stack": stack,
        "level": level,
        "package": package,
        "message": message
    }
 
    try:
        response = requests.post(LOG_API_URL, json=payload, headers=headers)
        result = response.json()
        print(f"[LOG SUCCESS] logID: {result.get('logID')} | {level.upper()} | {package} | {message}")
        return result
    except Exception as e:
        print(f"[LOG EXCEPTION] Failed to send log: {e}")
        return None
 
 
# Test the logger
if __name__ == "__main__":
    # Test 1 - error log
    Log("backend", "error", "handler", "received string, expected bool")
 
    # Test 2 - fatal db log
    Log("backend", "fatal", "db", "Critical database connection failure.")
 
    # Test 3 - info log
    Log("backend", "info", "service", "Vehicle scheduler started successfully.")
 
    # Test 4 - warn log
    Log("backend", "warn", "middleware", "Request rate limit approaching threshold.")