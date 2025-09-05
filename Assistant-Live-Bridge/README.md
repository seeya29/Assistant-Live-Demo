# Assistant Live-Bridge v1: API + DB Integrated Summarizer & Cognitive Agent

A single, live-ready pipeline that merges Seeya’s SmartBrief (summarization, intent/urgency) with Sankalp’s Cognitive Agent (task creation, scheduling, prioritization). It exposes a clean REST API, provides a Streamlit demo dashboard, and supports MongoDB/PostgreSQL or demo (in-memory) persistence.


## What this project does (in one glance)
- Ingest a raw message (email/WhatsApp/Slack/Teams/etc.)
- Summarize it with context, determine intent and urgency
- Convert the summary into a structured task with schedule/priority and recommendations
- Persist messages, summaries, and tasks in a DB (or demo memory)
- Provide endpoints and a dashboard for demos, testing, and operations


## Key capabilities
- Context-aware summarization (SmartBrief v3, with conversation history)
- Intent and urgency detection (deterministic patterns + context signals)
- Task creation (ContextFlow): classification, scheduling (dateparser), priority, recommendations
- REST API: /summarize, /process_summary, /pipeline, /feedback (+ /health, /stats, /metrics)
- Dashboards:
  - Streamlit (live API, simulated fallback)
  - Static offline snapshot (for firewall-restricted demos)
- Database support: MongoDB/PostgreSQL (or demo mode)
- Security and ops features: API key (optional), configurable CORS, lightweight JSON metrics


## Architecture
```
Assistant Live-Bridge
├── FastAPI app (main.py)
│   ├── POST /summarize         # Message → Summary (intent, urgency)
│   ├── POST /process_summary   # Summary → Task (schedule, priority, recommendations)
│   ├── POST /pipeline          # Message → Summary → Task (one call)
│   ├── POST /feedback          # Upvote/downvote to improve summarization
│   ├── GET  /users/{id}/tasks  # Retrieve tasks per user
│   ├── GET  /health, /stats    # Health & stats
│   └── GET  /metrics           # Lightweight JSON metrics
├── Summarizer (smart_summarizer_v3.py + smart_summarizer_api.py)
├── Context handling (context_loader.py + context_tracker.py)
├── Cognitive Agent & Flow (cognitive_agent.py + flow_handler.py + cognitive_agent_api.py)
└── Database layer (database_config.py) with MongoDB/PostgreSQL + demo mode
```

Data flow:
1) POST /summarize → stores message → runs SmartBrief → stores summary → returns summary JSON
2) POST /process_summary → runs ContextFlow → stores task → returns task JSON
3) Optional: use POST /pipeline to do both in one call
4) Optional: POST /feedback → logs feedback for future improvements


## Folder overview (consolidated)
This README belongs to the consolidated folder:
```
Assistant Live-Bridge/
├── main.py                   # FastAPI entrypoint
├── smart_summarizer_v3.py    # Summarizer engine (context-aware)
├── smart_summarizer_api.py   # API wrapper for summarizer
├── context_loader.py         # Conversation history and user context
├── context_tracker.py        # Context summaries, scoring, insights
├── cognitive_agent.py        # Agent (RL stubs + heuristics)
├── flow_handler.py           # Task creation: type, schedule, priority, recs
├── cognitive_agent_api.py    # API wrapper for task creation
├── database_config.py        # DB layer (Mongo/Postgres/Demo)
├── demo_streamlit_app.py     # Streamlit demo dashboard
├── test_integration.py       # End-to-end pipeline test
├── schema.md                 # DB schema documentation
├── requirements.txt          # Dependencies
├── .env.example              # Configuration template
├── user_contexts/            # (runtime) per-user context files
├── task_queue.json           # (runtime) file-backed queue (legacy/dashboard)
├── dashboard_logs.json       # (runtime) dashboard log stream
├── summarizer_learning.json  # (runtime) summarizer learning trace
├── agent_memory.json         # (runtime) cognitive agent memory
└── static_dashboard/         # Offline, static dashboard snapshot
```


## Quick Start (Windows)
Prerequisites:
- Python 3.9+ and pip
- Optional: MongoDB or PostgreSQL (otherwise use demo mode)

1) Open a terminal in this project folder
- File Explorer → right-click folder → Open in Terminal

2) Create and activate a virtual environment
- PowerShell
```
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
```
- Command Prompt (cmd)
```
python -m venv .venv
.venv\Scripts\activate
```

3) Install dependencies
```
pip install -r requirements.txt
```

4) Create configuration from template
```
copy .env.example .env
```
- For demos: make sure `.env` has `DATABASE_TYPE=demo` (no DB server required).

5) Run the API
```
python -B main.py
```
- Default URL: http://127.0.0.1:8000
- Health check: http://127.0.0.1:8000/health
- Optional env vars before running (PowerShell):
```
$env:API_HOST = "127.0.0.1"
$env:API_PORT = "8000"
# then
python -B main.py
```

6) (Optional) Run the Streamlit Demo Dashboard
In a new terminal window (with the venv activated):
```
streamlit run demo_streamlit_app.py --server.address 127.0.0.1 --server.port 8506
```
Open http://127.0.0.1:8506

7) (Optional) Static offline dashboard
Open the file directly in a browser:
```
static_dashboard/index.html
```


## Using the API (simplest path)
Supported platforms (example values): email, whatsapp, instagram, telegram, slack, teams

1) Health check
```
curl http://127.0.0.1:8000/health
```

2) Full pipeline in one call (message → summary → task)
```
curl -X POST http://127.0.0.1:8000/pipeline \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice_work",
    "platform": "email",
    "message_text": "Please schedule a review meeting next Tuesday at 3 PM.",
    "timestamp": "2025-09-02T10:00:00Z",
    "message_id": "manual_pipe_001"
  }'
```
Typical response contains success, summary data, and the created task.

3) Retrieve tasks for a user
```
curl http://127.0.0.1:8000/users/alice_work/tasks
```

Optional advanced (two-step):
- Step A: Summarize only
```
curl -X POST http://127.0.0.1:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice_work",
    "platform": "email",
    "message_text": "Please schedule a review meeting next Tuesday at 3 PM.",
    "timestamp": "2025-09-02T10:00:00Z",
    "message_id": "manual_test_001"
  }'
```
- Step B: Create a task from the returned summary
```
curl -X POST http://127.0.0.1:8000/process_summary \
  -H "Content-Type: application/json" \
  -d '{
    "summary_id": "<from_previous_response>",
    "user_id": "alice_work",
    "platform": "email",
    "summary": "Schedule review meeting next Tuesday at 3 PM",
    "intent": "meeting",
    "urgency": "medium",
    "original_message": "Please schedule a review meeting next Tuesday at 3 PM."
  }'
```

Security (optional):
- Enable in the API shell before running:
```
$env:API_REQUIRE_KEY = "true"
$env:API_KEY = "demo-key"
python -B main.py
```
- Then send with requests: `-H "x-api-key: demo-key"`


## Task creation details
- Scheduling: uses dateparser (e.g., “in 2 hours”, “tomorrow 9am”, “next Friday at 4pm”) with message timestamp as RELATIVE_BASE.
- Priority: derived from urgency and keywords (urgent/asap/etc.).
- Recommendations: sorted actions like calendar_block, send_confirmation, reminders.
- Status updates: DB-backed via DatabaseManager.update_task_status; endpoint PUT /tasks/{id}/status.


## Database
Three entities, whether MongoDB or PostgreSQL:
- messages: user_id, platform, message_text, timestamp, message_id, metadata
- summaries: summary_id, message_id, user_id, platform, summary, intent, urgency, confidence, reasoning
- tasks: task_id, summary_id, user_id, platform, task_summary, task_type, scheduled_for, status, priority, recommendations

Demo mode (default):
- Set `DATABASE_TYPE=demo` in .env (no DB server required)

MongoDB example .env:
```
DATABASE_TYPE=mongodb
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DATABASE=smartbrief_cognitive_agent
```

PostgreSQL example .env:
```
DATABASE_TYPE=postgresql
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=smartbrief_cognitive_agent
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```


## Streamlit dashboard (live demo)
- Start API, then:
```
streamlit run demo_streamlit_app.py --server.address 127.0.0.1 --server.port 8506
```
- Features:
  - Load Demo Messages → Summarize / Full Pipeline
  - Summaries tab → reasoning, intent, urgency
  - Tasks tab → priorities, schedules, recommendations
  - API Testing tab → live endpoint testing
- If API is offline or blocked, the dashboard automatically falls back to Simulated Mode.

Static dashboard (offline):
```
static_dashboard/index.html
```


## Integration test (end-to-end)
```
python test_integration.py
```
- Verifies:
  - /health
  - /summarize → returns summary JSON
  - /process_summary → returns task JSON and persists task
  - /users/{id}/tasks includes the created task
  - /feedback works


## Troubleshooting
- “API Offline” in Streamlit:
  - Ensure API is running from the project folder
  - Use 127.0.0.1 (not localhost)
  - Check http://127.0.0.1:8000/health
- HTTP 400: Platform must be one of …
  - Use one of: email, whatsapp, instagram, telegram, slack, teams
- HTTP 400: timestamp invalid
  - Use ISO 8601 with Z, e.g., "2025-09-02T10:00:00Z"
- FileNotFoundError user_contexts/…
  - Run API from project root; it creates user_contexts and uses absolute paths
  - If needed, create an empty file `{}` in user_contexts/<user>_context.json
- API key enabled but requests failing
  - Set API_KEY in both API and client shells; Streamlit sends x-api-key automatically if set
- Stale code behavior
  - Stop processes, delete __pycache__, run API with `python -B main.py`


## Deployment (basic)
- Production process:
```
pip install -r requirements.txt
# Configure DB and security in .env
$env:API_DEBUG = "false"; $env:DATABASE_TYPE = "mongodb"  # or postgresql
python -B main.py  # or uvicorn/gunicorn workers
```
- Docker (base image example):
```
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "main.py"]
```


## Roadmap
- Recommendation scoring and sorting improvements
- CI with DB matrix (Mongo/Postgres) + negative-path tests
- Prometheus/OpenTelemetry metrics
- Authentication/authorization for non-dev
- docker-compose for one-command API+DB+dashboard spin-up

---

With Assistant Live-Bridge, managers and engineers can go from raw messages to actionable tasks in minutes, with a live API, dashboards, and clear operational guidance. This README now includes streamlined setup and API usage so you can run locally with minimal steps.