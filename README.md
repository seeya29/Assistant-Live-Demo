# Assistant Live Demo

Runnable pipeline and minimal tester that turns a single message into a summary and an actionable task, with feedback capture. This repository includes a ready-to-run FastAPI service, a small Streamlit front-end for manual testing, automated integration tests, and sample data.

One-line architecture:
```
[Streamlit (localhost:8501)] → (HTTP) → [FastAPI /api (localhost:8000)] ↔ [SQLite assistant_demo.db]
```

---

## Repository Structure
```
assistant-live-demo/
├─ api/
│  └─ main.py                 # FastAPI app: /api/health, /api/summarize, /api/process_summary, /api/feedback
├─ streamlit/
│  └─ demo_streamlit.py       # Minimal front-end: send message → summary → task, post feedback
├─ tests/
│  └─ test_integration.py     # End-to-end test script (requires API running)
├─ data/
│  └─ sample_messages.json    # ≥5 sample inputs (WhatsApp, Instagram, Email)
├─ ScreenShots/
│  └─ demo.png                # Evidence (or multiple PNGs)
├─ ScreenRecordings/
│  └─ demo.mp4                # Optional 60–90s screen-recorded clip
├─ VALUES.md                  # Short reflection: Humility / Gratitude / Honesty
├─ requirements.txt           # Python dependencies for API + Streamlit + tests
└─ README.md                  # Component-level README for the demo app
```
Note: All deliverables live under assistant-live-demo/. If you’re viewing this file at the repository root, the paths above refer to that subfolder.

---

## Quick Start

Prerequisites: Python 3.9+

Recommended: use a virtual environment.

- Windows (PowerShell/CMD)
```
cd assistant-live-demo
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

- macOS/Linux
```
cd assistant-live-demo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start the API (Terminal 1):
```
cd assistant-live-demo && uvicorn api.main:app --reload --port 8000
```
Health check: http://127.0.0.1:8000/api/health

Start the Streamlit tester (Terminal 2):
```
cd assistant-live-demo && streamlit run streamlit/demo_streamlit.py
```

Run the end-to-end test (Terminal 3, API must be running):
```
cd assistant-live-demo && python tests/test_integration.py
```

---

## What the Demo Does
- Accepts a raw message (user_id, platform, message_text, timestamp, optional conversation_id) and stores it.
- Generates a concise summary (type, intent, urgency); stores the summary.
- Creates a task (task_type, schedule hint, status) from the summary; stores the task.
- Records feedback (up/down + optional comment) for each summary.
- Shows live DB tables in the Streamlit tester: Messages | Summaries | Tasks.

---

## API Contracts

All IDs are server-generated (UUID4 or equivalent). Clients do NOT supply message_id, summary_id, or task_id. Timestamps are ISO8601 strings (UTC recommended, e.g., `2025-09-01T10:00:00Z`).

- Accepted enum values:
  - platform: `whatsapp`, `instagram`, `email`
  - summary.type: `follow-up`, `meeting`, `request`
  - summary.urgency: `low`, `medium`, `high`
  - task.task_type: `meeting`, `reminder`, `follow-up`
  - feedback.rating: `up`, `down`

- GET /api/health
```
Response: { "status": "ok" }
```

- POST /api/summarize
```
Request (message.json):
{
  "user_id": "abc123",
  "platform": "whatsapp|instagram|email",
  "conversation_id": "conv001",
  "message_text": "string",
  "timestamp": "ISO8601"
}

Response (summary.json):
{
  "message_id": "m_generated",               // server-generated
  "summary_id": "s_generated",               // server-generated
  "summary": "User is following up on report status.",
  "type": "follow-up|meeting|request",
  "intent": "check progress",
  "urgency": "low|medium|high",
  "timestamp": "ISO8601"                      // processing time
}
```

- POST /api/process_summary
```
Request:
{
  "summary_id": "s_generated"
}

Response (task.json):
{
  "task_id": "t_generated",                  // server-generated
  "user_id": "abc123",
  "task_summary": "Finalize slides",
  "task_type": "meeting|reminder|follow-up",
  "scheduled_for": "2025-09-07T16:00:00Z",
  "status": "pending"
}
```

- POST /api/feedback
```
Request (feedback.json):
{
  "summary_id": "s_generated",
  "rating": "up|down",
  "comment": "optional",
  "timestamp": "ISO8601"
}

Response:
{ "ok": true }
```

Validation & Security:
- Requests are validated using Pydantic models.
- All DB operations use parameterized SQL to prevent injection.
- The Streamlit app calls the API server-side (no browser CORS configuration required).
- Basic error handling returns 4xx for validation errors and 5xx for unexpected failures.

---

## Sample curl Commands

- Create summary (input message). Note: server generates message_id and summary_id.
```
curl -X POST http://127.0.0.1:8000/api/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u1",
    "platform": "whatsapp",
    "conversation_id": "conv001",
    "message_text": "Hey, did the report get done?",
    "timestamp": "2025-09-01T10:00:00Z"
  }'
```

- Create task from summary (replace s_generated with actual summary_id returned above)
```
curl -X POST http://127.0.0.1:8000/api/process_summary \
  -H "Content-Type: application/json" \
  -d '{
    "summary_id": "s_generated"
  }'
```

- Post feedback (replace s_generated)
```
curl -X POST http://127.0.0.1:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "summary_id": "s_generated",
    "rating": "up",
    "comment": "good",
    "timestamp": "2025-09-01T10:01:00Z"
  }'
```

---

## Database

- SQLite file: `assistant-live-demo/assistant_demo.db`
- Tables are auto-created on API startup if not present.
- Canonical schema (SQLite):

```sql
CREATE TABLE IF NOT EXISTS messages (
  message_id    TEXT PRIMARY KEY,
  user_id       TEXT NOT NULL,
  platform      TEXT NOT NULL CHECK (platform IN ('whatsapp','instagram','email')),
  conversation_id TEXT,
  message_text  TEXT NOT NULL,
  timestamp     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS summaries (
  summary_id    TEXT PRIMARY KEY,
  message_id    TEXT NOT NULL,
  summary       TEXT NOT NULL,
  type          TEXT NOT NULL CHECK (type IN ('follow-up','meeting','request')),
  intent        TEXT NOT NULL,
  urgency       TEXT NOT NULL CHECK (urgency IN ('low','medium','high')),
  timestamp     TEXT NOT NULL,
  FOREIGN KEY (message_id) REFERENCES messages(message_id)
);

CREATE TABLE IF NOT EXISTS tasks (
  task_id       TEXT PRIMARY KEY,
  user_id       TEXT NOT NULL,
  task_summary  TEXT NOT NULL,
  task_type     TEXT NOT NULL CHECK (task_type IN ('meeting','reminder','follow-up')),
  scheduled_for TEXT,
  status        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  summary_id   TEXT NOT NULL,
  rating       TEXT NOT NULL CHECK (rating IN ('up','down')),
  comment      TEXT,
  timestamp    TEXT NOT NULL,
  FOREIGN KEY (summary_id) REFERENCES summaries(summary_id)
);
```

Column names are standardized to `message_text` (not `text`).

---

## Streamlit Tester (functional checklist)
- Form fields: user_id, platform, message_text, Send button.
- On send: summary card is shown; then task card is shown automatically.
- Tabs showing live tables (Messages | Summaries | Tasks) with a Refresh button.
- Up/Down buttons to submit feedback next to each summary.
- Inline logs/errors shown near the relevant steps.

Implementation notes:
- Streamlit calls the API from the Python backend (server-side requests); no CORS setup is needed.
- The API base URL defaults to `http://127.0.0.1:8000`.

---

## Testing

End-to-end test: `tests/test_integration.py` asserts that:
1) POST /api/summarize returns a `summary_id` (and `message_id`).
2) POST /api/process_summary returns a `task_id` and persists the task.
3) POST /api/feedback stores a feedback row in the DB.

Before running tests, ensure the API is running.

Command:
```
cd assistant-live-demo && python tests/test_integration.py
```

---

## Sample Data

- `data/sample_messages.json` includes at least 5 messages covering WhatsApp, Instagram, and Email. Example format:
```
[
  {"user_id":"u1","platform":"whatsapp","conversation_id":"c1","message_text":"Hey, status?","timestamp":"2025-09-01T10:00:00Z"},
  {"user_id":"u2","platform":"instagram","conversation_id":"c2","message_text":"Let's schedule a meeting","timestamp":"2025-09-01T12:00:00Z"},
  {"user_id":"u3","platform":"email","conversation_id":"c3","message_text":"Please send the report","timestamp":"2025-09-01T13:00:00Z"},
  {"user_id":"u4","platform":"whatsapp","conversation_id":"c4","message_text":"Reminder for tomorrow","timestamp":"2025-09-02T09:00:00Z"},
  {"user_id":"u5","platform":"instagram","conversation_id":"c5","message_text":"Follow up on invoice","timestamp":"2025-09-02T11:30:00Z"}
]
```

---

## Evidence

Add 1–2 screenshots or a 60–90s screen-recorded clip demonstrating:
- Creating a summary and task from a message
- Posting feedback

Place assets here:
- Screenshots: `assistant-live-demo/ScreenShots/*.png`
- Video (optional): `assistant-live-demo/ScreenRecordings/*.mp4`

---

## Values

See `assistant-live-demo/VALUES.md` for a brief reflection (Humility / Gratitude / Honesty).

---

## Notes
- The demo uses lightweight heuristics for summary classification and schedule hints, optimized for speed and clarity.
- The API and tester are intentionally minimal for easy review and extension.

---

## License

MIT. Consider adding a `LICENSE` file at the repository root identifying the MIT License terms.
