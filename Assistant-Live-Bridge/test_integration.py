import os
import sys
import time
import json
from datetime import datetime

import requests

BASE_URL = os.getenv("TEST_API_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("API_KEY")
HEADERS = {"x-api-key": API_KEY} if API_KEY else {}


def require(status_ok: bool, msg: str):
    if not status_ok:
        print(f"[FAIL] {msg}")
        sys.exit(1)
    print(f"[OK] {msg}")


def main():
    user_id = "integration_test_user"
    platform = "email"
    message_text = "Please schedule a project review meeting next Tuesday at 3 PM."

    # 1) Health check
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=10)
        if r.status_code != 200:
            # try versioned path
            r = requests.get(f"{BASE_URL}/v1/health", timeout=10)
        require(r.status_code == 200, f"API health check (status={r.status_code})")
    except Exception as e:
        print(f"[FAIL] API not reachable at {BASE_URL} -> {e}")
        sys.exit(1)

    # 2) POST /summarize
    message_payload = {
        "user_id": user_id,
        "platform": platform,
        "message_text": message_text,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "message_id": f"testmsg_{int(time.time())}"
    }

    r = requests.post(f"{BASE_URL}/summarize", json=message_payload, headers=HEADERS, timeout=30)
    require(r.status_code == 200, f"/summarize returned 200 (got {r.status_code}, body={r.text[:300]})")
    summary = r.json()

    # 3) POST /process_summary
    summary_payload = {
        "summary_id": summary.get("summary_id"),
        "user_id": user_id,
        "platform": platform,
        "summary": summary.get("summary"),
        "intent": summary.get("intent"),
        "urgency": summary.get("urgency"),
        "type": summary.get("type"),
        "confidence": summary.get("confidence"),
        "reasoning": summary.get("reasoning", []),
        "context_used": summary.get("context_used", False),
        "original_message": message_text
    }

    r2 = requests.post(f"{BASE_URL}/process_summary", json=summary_payload, headers=HEADERS, timeout=30)
    require(r2.status_code == 200, f"/process_summary returned 200 (got {r2.status_code}, body={r2.text[:300]})")
    task = r2.json()

    # 4) GET /users/{user_id}/tasks
    r3 = requests.get(f"{BASE_URL}/users/{user_id}/tasks", timeout=20)
    require(r3.status_code == 200, f"/users/{{user_id}}/tasks returned 200 (got {r3.status_code})")
    tasks = r3.json().get("tasks", [])
    require(any(t.get("task_id") == task.get("task_id") for t in tasks), "Created task present in user task list")

    # 5) Optional feedback
    fb = {
        "summary_id": summary.get("summary_id"),
        "feedback": "upvote",
        "comment": "Integration test auto-feedback"
    }
    rf = requests.post(f"{BASE_URL}/feedback", json=fb, headers=HEADERS, timeout=15)
    require(rf.status_code == 200, f"/feedback returned 200 (got {rf.status_code})")

    # Print pipeline result
    pipeline = {
        "message": message_payload,
        "summary": summary,
        "task": task,
        "task_count": len(tasks)
    }
    print("\n=== Pipeline Result (Message → Summary → Task) ===")
    print(json.dumps(pipeline, indent=2))
    print("\nAll integration steps completed successfully.")


if __name__ == "__main__":
    main()
