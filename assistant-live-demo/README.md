# Assistant Live Demo

Runnable demo pipeline: one message → summary → task with feedback.

One-line architecture:
```
[Streamlit Tester] → (HTTP) → [FastAPI /api] ↔ [SQLite assistant_demo.db]
```

## Run Steps
Prereqs: Python 3.9+
```
cd assistant-live-demo
pip install -r requirements.txt

# API (terminal 1)
uvicorn api.main:app --reload --port 8000

# Streamlit (terminal 2)
streamlit run streamlit/demo_streamlit.py

# Integration test (terminal 3)
python tests/test_integration.py
```

## API Endpoints
- POST /api/summarize
  - Input message.json
  - Returns summary.json and stores in DB
- POST /api/process_summary
  - Input summary.json
  - Returns task.json and stores in DB
- POST /api/feedback
  - Input feedback { summary_id, rating: "up"|"down", comment?, timestamp }

Contracts:
- message.json
```
{
  "user_id":"abc123",
  "platform":"whatsapp|instagram|email",
  "conversation_id":"conv001",
  "message_id":"m123",
  "message_text":"string",
  "timestamp":"ISO8601"
}
```
- summary.json (returned by /api/summarize)
```
{
  "summary_id":"s123",
  "message_id":"m123",
  "summary":"User is following up on report status.",
  "type":"follow-up|meeting|request",
  "intent":"check progress",
  "urgency":"low|medium|high",
  "timestamp":"ISO8601"
}
```
- task.json (returned by /api/process_summary)
```
{
  "task_id":"t123",
  "user_id":"abc123",
  "task_summary":"Finalize slides",
  "task_type":"meeting|reminder|follow-up",
  "scheduled_for":"2025-09-07T16:00:00Z",
  "status":"pending"
}
```
- feedback.json
```
{ "summary_id":"s123", "rating":"up|down", "comment":"optional", "timestamp":"ISO8601" }
```

## Streamlit Tester
- Form: user_id, platform, message_text, Send.
- On Send: POST /api/summarize → show summary; auto-call /api/process_summary → show task.
- Live tables (from SQLite): Messages, Summaries, Tasks (Refresh button).
- Up/Down buttons on summaries to POST /api/feedback; show confirmation messages.
- Minimal errors/logs at top of the page.

## Integration Test
```
python tests/test_integration.py
```
- Posts sample message → asserts summary_id.
- Posts summary → asserts task_id.
- Verifies DB rows exist.
- Posts feedback → asserts success.
- Prints Message → Summary → Task chain.

## Sample Data
- data/sample_messages.json includes 5 sample messages: WhatsApp, Instagram, Email.

## DB Schema (SQLite: assistant_demo.db)
- messages(message_id PK, user_id, platform, conversation_id, text, timestamp)
- summaries(summary_id PK, message_id FK, summary, type, intent, urgency, timestamp)
- tasks(task_id PK, user_id, task_summary, task_type, scheduled_for, status)
- feedback(id PK, summary_id FK, rating, comment, timestamp)

## Curl commands
- Summarize:
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
- Process summary:
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
- Feedback:
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

## Evidence
- Add 1–2 screenshots or a short 60–90s clip of the tester in action.

## VALUES.md
- Reflection (Humility / Gratitude / Honesty) required. See VALUES.md.

---

## Spec compliance (Assistant Live Demo)

This demo implements the requested pipeline end-to-end. Summary of how each requirement is satisfied:

1) API (FastAPI)
- POST /api/summarize
  - Accepts JSON { user_id, platform, conversation_id, message_id, message_text, timestamp }
  - Uses lightweight heuristics to produce a concise summary and simple classification (type/intent/urgency)
  - Persists the original message (messages) and the summary (summaries)
  - Returns a JSON body including summary_id
- POST /api/process_summary
  - Accepts the summary JSON (incl. summary_id)
  - Generates a task with naive schedule inference and type selection
  - Persists the task (tasks)
  - Returns a JSON body including task_id
- POST /api/feedback
  - Accepts { summary_id, rating: "up"|"down", comment?, timestamp }
  - Persists feedback linked to summaries

2) Database (SQLite)
- File: assistant-live-demo/assistant_demo.db (auto-created by the API)
- Actual schema in this demo uses string IDs for convenience and clarity:
  - messages(message_id TEXT PRIMARY KEY, user_id TEXT, platform TEXT, conversation_id TEXT, text TEXT, timestamp TEXT)
  - summaries(summary_id TEXT PRIMARY KEY, message_id TEXT REFERENCES messages(message_id), summary TEXT, type TEXT, intent TEXT, urgency TEXT, timestamp TEXT)
  - tasks(task_id TEXT PRIMARY KEY, user_id TEXT, task_summary TEXT, task_type TEXT, scheduled_for TEXT, status TEXT)
  - feedback(id INTEGER PRIMARY KEY AUTOINCREMENT, summary_id TEXT REFERENCES summaries(summary_id), rating TEXT, comment TEXT, timestamp TEXT)
- Note: While your outline suggests integer autoincrement IDs, this demo uses short string IDs to keep the payloads self-describing and quick to test. The README above documents both the contracts and the actual persisted fields.

3) Streamlit Tester
- Input form for user_id, platform, message_text; on submit:
  - Calls /api/summarize and shows a summary card
  - Immediately calls /api/process_summary and shows a task card
- Data visualization: live Messages | Summaries | Tasks tabs, with a Refresh button
- Feedback: Up/Down buttons next to summaries post to /api/feedback

4) Testing
- End-to-end test script: assistant-live-demo/tests/test_integration.py
  - Verifies summarize → process_summary → DB rows → feedback

5) Sample Data & Documentation
- Sample data: assistant-live-demo/data/sample_messages.json (5+ messages: WhatsApp, Instagram, Email)
- Documentation: this README includes run steps, API contracts, and curl examples
- VALUES.md: included at assistant-live-demo/VALUES.md
- Evidence: screenshots in assistant-live-demo/ScreenShots

Run commands (quick reference)
- Install deps: pip install -r assistant-live-demo/requirements.txt
- Start API: uvicorn api.main:app --reload --port 8000 (run from assistant-live-demo)
- Start Streamlit: streamlit run streamlit/demo_streamlit.py (run from assistant-live-demo)
- Run tests: python assistant-live-demo/tests/test_integration.py (API must be running)

These additions clarify the mapping from requirements to the working demo without altering the functioning code.
