# Assistant Live Demo

Runnable pipeline and minimal tester that turns a single message into a summary and an actionable task, with feedback capture. This repository includes a ready-to-run FastAPI service, a small Streamlit front-end for manual testing, automated integration tests, and sample data.

One-line architecture:
```
[Streamlit Tester] → (HTTP) → [FastAPI /api] ↔ [SQLite assistant_demo.db]
```

## Repository Structure
```
assistant-live-demo/
├─ api/
│  └─ main.py                 # FastAPI app: /api/summarize, /api/process_summary, /api/feedback
├─ streamlit/
│  └─ demo_streamlit.py       # Minimal front-end: send message → summary → task, post feedback
├─ tests/
│  └─ test_integration.py     # End-to-end test script (requires API running)
├─ data/
│  └─ sample_messages.json    # 5 sample inputs (WhatsApp, Instagram, Email)
├─ VALUES.md                  # Short reflection: Humility / Gratitude / Honesty
├─ requirements.txt           # Python dependencies for API + Streamlit + tests
└─ README.md                  # Component-level README for the demo app
```

## Quick Start
Prerequisites: Python 3.9+

1) Install dependencies
```
cd assistant-live-demo
pip install -r requirements.txt
```

2) Start the API (terminal 1)
```
uvicorn api.main:app --reload --port 8000
```
Health check: http://127.0.0.1:8000/api/health

3) Start the Streamlit tester (terminal 2)
```
streamlit run streamlit/demo_streamlit.py
```

4) Run the end-to-end test (terminal 3)
```
python tests/test_integration.py
```

## What the Demo Does
- Accepts a raw message (user_id, platform, text, timestamp) and stores it.
- Generates a concise summary with type, intent, urgency; stores the summary.
- Creates a task (type, schedule hint, status) from the summary; stores the task.
- Records feedback (up/down + optional comment) for each summary.
- Shows live DB tables in the Streamlit tester: Messages | Summaries | Tasks.

## API Contracts
- message.json (POST /api/summarize)
```
{
  "user_id": "abc123",
  "platform": "whatsapp|instagram|email",
  "conversation_id": "conv001",
  "message_id": "m123",
  "message_text": "string",
  "timestamp": "ISO8601"
}
```
- summary.json (returned by /api/summarize and input to /api/process_summary)
```
{
  "summary_id": "s123",
  "message_id": "m123",
  "summary": "User is following up on report status.",
  "type": "follow-up|meeting|request",
  "intent": "check progress",
  "urgency": "low|medium|high",
  "timestamp": "ISO8601"
}
```
- task.json (returned by /api/process_summary)
```
{
  "task_id": "t123",
  "user_id": "abc123",
  "task_summary": "Finalize slides",
  "task_type": "meeting|reminder|follow-up",
  "scheduled_for": "2025-09-07T16:00:00Z",
  "status": "pending"
}
```
- feedback.json (POST /api/feedback)
```
{
  "summary_id": "s123",
  "rating": "up|down",
  "comment": "optional",
  "timestamp": "ISO8601"
}
```

## Sample curl Commands
- Create summary
```
curl -X POST http://127.0.0.1:8000/api/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "user_id":"u1",
    "platform":"whatsapp",
    "conversation_id":"conv001",
    "message_id":"m123",
    "message_text":"Hey, did the report get done?",
    "timestamp":"2025-09-01T10:00:00Z"
  }'
```
- Create task from summary
```
curl -X POST http://127.0.0.1:8000/api/process_summary \
  -H "Content-Type: application/json" \
  -d '{
    "summary_id":"s123",
    "message_id":"m123",
    "summary":"User is following up on status.",
    "type":"follow-up",
    "intent":"check progress",
    "urgency":"low",
    "timestamp":"2025-09-01T10:00:10Z"
  }'
```
- Post feedback
```
curl -X POST http://127.0.0.1:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "summary_id":"s123",
    "rating":"up",
    "comment":"good",
    "timestamp":"2025-09-01T10:01:00Z"
  }'
```

## Database
SQLite file: assistant-live-demo/assistant_demo.db

Schema (minimum):
- messages(message_id PK, user_id, platform, conversation_id, text, timestamp)
- summaries(summary_id PK, message_id FK, summary, type, intent, urgency, timestamp)
- tasks(task_id PK, user_id, task_summary, task_type, scheduled_for, status)
- feedback(id PK, summary_id FK, rating, comment, timestamp)

## Streamlit Tester (functional checklist)
- Form fields: user_id, platform, message_text, Send button.
- On send: summary card is shown; then task card is shown automatically.
- Tabs showing live tables (Messages | Summaries | Tasks) with a Refresh button.
- Up/Down buttons to submit feedback next to each summary.
- Inline logs/errors shown near the relevant steps.

## Evidence
Add 1–2 screenshots or a 60–90s screen-recorded clip demonstrating:
- Creating a summary and task from a message
- Posting feedback

## Values
See `assistant-live-demo/VALUES.md` for a brief reflection (Humility / Gratitude / Honesty).

## Notes
- The demo uses lightweight heuristics for summary classification and schedule hints, optimized for speed and clarity.
- The API and tester are intentionally minimal for easy review and extension.

## License
MIT (or project’s default). Update as needed.
