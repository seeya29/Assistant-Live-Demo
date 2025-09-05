import os
import time
import sqlite3
import json
from datetime import datetime

import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, "assistant_demo.db")
API = os.getenv("API", "http://127.0.0.1:8000")


def now_iso():
    return datetime.utcnow().isoformat() + "Z"


def test_pipeline():
    # 1) POST sample message
    message = {
        "user_id": "abc123",
        "platform": "whatsapp",
        "conversation_id": "conv001",
        "message_id": f"m_{int(time.time())}",
        "message_text": "Can we reschedule the review to next Monday?",
        "timestamp": now_iso(),
    }
    r1 = requests.post(f"{API}/api/summarize", json=message, timeout=20)
    assert r1.status_code == 200, r1.text
    summary = r1.json()
    assert "summary_id" in summary and summary["summary_id"], "summary_id missing"

    # 2) POST summary to process_summary
    summary_payload = {
        "summary_id": summary["summary_id"],
        "message_id": summary["message_id"],
        "summary": summary["summary"],
        "type": summary["type"],
        "intent": summary["intent"],
        "urgency": summary["urgency"],
        "timestamp": summary["timestamp"],
    }
    r2 = requests.post(f"{API}/api/process_summary", json=summary_payload, timeout=20)
    assert r2.status_code == 200, r2.text
    task = r2.json()
    assert "task_id" in task and task["task_id"], "task_id missing"

    # 3) Query DB to verify entries exist
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM messages WHERE message_id = ?", (message["message_id"],))
        assert cur.fetchone()[0] == 1, "message not stored"
        cur.execute("SELECT COUNT(*) FROM summaries WHERE summary_id = ?", (summary["summary_id"],))
        assert cur.fetchone()[0] == 1, "summary not stored"
        cur.execute("SELECT COUNT(*) FROM tasks WHERE task_id = ?", (task["task_id"],))
        assert cur.fetchone()[0] == 1, "task not stored"
    finally:
        conn.close()

    # 4) Post feedback
    feedback = {"summary_id": summary["summary_id"], "rating": "up", "timestamp": now_iso()}
    r3 = requests.post(f"{API}/api/feedback", json=feedback, timeout=20)
    assert r3.status_code == 200, r3.text

    # 5) Print chain
    chain = {
        "message": message,
        "summary": summary,
        "task": task,
    }
    print("\n=== Message → Summary → Task ===")
    print(json.dumps(chain, indent=2))


if __name__ == "__main__":
    test_pipeline()
    print("\nIntegration test completed successfully.")
