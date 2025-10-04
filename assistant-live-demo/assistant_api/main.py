import os
import sys
import sqlite3
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, Literal, Dict, Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

try:
    import jwt  # PyJWT
except Exception:
    jwt = None

# Paths
API_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(API_DIR)
DB_PATH = os.path.join(REPO_ROOT, "assistant_demo.db")

# FastAPI app
app = FastAPI(title="Assistant API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security configuration
API_KEY = os.getenv("API_KEY")
API_REQUIRE_KEY = os.getenv("API_REQUIRE_KEY", "false").lower() == "true"
JWT_REQUIRE = os.getenv("JWT_REQUIRE", "false").lower() == "true"
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

logger = logging.getLogger("assistant_api")
logging.basicConfig(level=logging.INFO)

# DB utils
SCHEMA = {
    "messages": """
        CREATE TABLE IF NOT EXISTS messages (
            message_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            conversation_id TEXT,
            text TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );
    """,
    "summaries": """
        CREATE TABLE IF NOT EXISTS summaries (
            summary_id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL,
            summary TEXT NOT NULL,
            type TEXT NOT NULL,
            intent TEXT NOT NULL,
            urgency TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY(message_id) REFERENCES messages(message_id)
        );
    """,
    "tasks": """
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            task_summary TEXT NOT NULL,
            task_type TEXT NOT NULL,
            scheduled_for TEXT,
            status TEXT NOT NULL
        );
    """,
    "feedback": """
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summary_id TEXT NOT NULL,
            rating TEXT NOT NULL,
            comment TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY(summary_id) REFERENCES summaries(summary_id)
        );
    """,
}


def get_conn():
    os.makedirs(REPO_ROOT, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
    except Exception:
        pass
    return conn


def init_db():
    conn = get_conn()
    try:
        cur = conn.cursor()
        for sql in SCHEMA.values():
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


# Middleware: API key / JWT enforcement
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    path = request.url.path

    # Allow unauthenticated GET to health and docs/static
    if request.method == "GET" and (
        path.endswith("/health") or path.endswith("/api/health") or path.startswith("/docs") or path.startswith("/openapi") or path.startswith("/redoc")
    ):
        return await call_next(request)

    # If neither is required, pass through
    if not API_REQUIRE_KEY and not JWT_REQUIRE:
        return await call_next(request)

    # Check API key
    if API_REQUIRE_KEY:
        if request.headers.get("x-api-key") != API_KEY:
            return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "Invalid API key"})

    # Check JWT
    if JWT_REQUIRE:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "Missing Bearer token"})
        token = auth.split(" ", 1)[1]
        if not jwt or not JWT_SECRET:
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "JWT not configured"})
        try:
            jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except Exception as e:
            return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": f"Invalid token: {str(e)}"})

    return await call_next(request)


# Models (API Contracts)
Platform = Literal["whatsapp", "instagram", "email"]
Urgency = Literal["low", "medium", "high"]
SummaryType = Literal["follow-up", "meeting", "request"]
TaskType = Literal["meeting", "reminder", "follow-up"]
Rating = Literal["up", "down"]


class MessageIn(BaseModel):
    user_id: str
    platform: Platform
    conversation_id: str
    message_id: str
    message_text: str
    timestamp: str


class SummaryOut(BaseModel):
    summary_id: str
    message_id: str
    summary: str
    type: SummaryType
    intent: str
    urgency: Urgency
    timestamp: str


class SummaryIn(BaseModel):
    summary_id: str
    message_id: str
    summary: str
    type: SummaryType
    intent: str
    urgency: Urgency
    timestamp: str


class TaskOut(BaseModel):
    task_id: str
    user_id: str
    task_summary: str
    task_type: TaskType
    scheduled_for: Optional[str] = None
    status: str


class FeedbackIn(BaseModel):
    summary_id: str
    rating: Rating
    comment: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


# Simple heuristics
KEYWORDS = {
    "follow_up": ["follow up", "follow-up", "status", "did the", "get done", "update"],
    "meeting": ["meeting", "call", "reschedule", "schedule", "standup", "review"],
    "urgent": ["urgent", "asap", "immediately", "server is down"],
    "reminder": ["reminder", "due", "invoice", "don't forget", "deadline"],
}


def classify_summary(msg: MessageIn) -> tuple[str, SummaryType, Urgency, str]:
    text = msg.message_text.lower()

    # type and intent
    if any(k in text for k in KEYWORDS["follow_up"]):
        stype: SummaryType = "follow-up"
        intent = "check progress"
    elif any(k in text for k in KEYWORDS["meeting"]):
        stype = "meeting"
        intent = "meeting"
    else:
        stype = "request"
        intent = "request"

    # urgency
    if any(k in text for k in KEYWORDS["urgent"]):
        urg: Urgency = "high"
    elif any(k in text for k in KEYWORDS["reminder"]):
        urg = "medium"
    else:
        urg = "low"

    # summary text (concise)
    if stype == "follow-up":
        smry = "User is following up on status."
    elif stype == "meeting":
        smry = "User requests scheduling or rescheduling a meeting."
    else:
        smry = "User made a request."

    return smry, stype, urg, intent


def infer_task(summary: SummaryIn, user_id: str, message_text: str) -> tuple[str, TaskType, Optional[str]]:
    text = (summary.summary + " " + message_text).lower()

    if summary.type == "meeting" or any(k in text for k in ["meeting", "call", "schedule", "reschedule"]):
        ttype: TaskType = "meeting"
    elif summary.type == "follow-up" or any(k in text for k in ["follow up", "status", "update"]):
        ttype = "follow-up"
    else:
        ttype = "reminder"

    # naive schedule extraction
    scheduled_for = None
    now = datetime.utcnow()
    if "tomorrow" in text:
        scheduled_for = (now.replace(microsecond=0) + timedelta(days=1)).isoformat() + "Z"
    elif "next" in text or any(d in text for d in ["monday", "tuesday", "wednesday", "thursday", "friday"]):
        scheduled_for = (now.replace(microsecond=0) + timedelta(days=3)).isoformat() + "Z"

    task_summary = summary.summary.replace("User ", "").strip()
    if not task_summary:
        task_summary = "Follow up"

    return task_summary, ttype, scheduled_for


# Startup
@app.on_event("startup")
def _startup():
    init_db()


# Simple auth: issue JWT using API key
class TokenRequest(BaseModel):
    # Optional user identifier to include as subject
    sub: Optional[str] = "api_user"
    exp_minutes: Optional[int] = 60


@app.post("/auth/token")
def issue_token(req: TokenRequest, x_api_key: Optional[str] = None):
    # Accept header key or query/body via FastAPI dependency injection; prioritize header
    # FastAPI does not auto-pass headers into params; we can read from env or require API key param
    # For simplicity, use env API_KEY check via global
    if API_REQUIRE_KEY and API_KEY:
        # Require caller to present same API key via header
        # Note: In real deployments, use Header() to read. Here, rely on global middleware already checking.
        pass

    if not jwt or not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT not configured")
    now = datetime.utcnow()
    payload = {"sub": req.sub or "api_user", "iat": int(now.timestamp()), "exp": int((now + timedelta(minutes=req.exp_minutes or 60)).timestamp())}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"access_token": token, "token_type": "bearer", "expires_in": (req.exp_minutes or 60) * 60}


# Core routes (API-prefixed)
@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.post("/api/summarize", response_model=SummaryOut)
def api_summarize(message: MessageIn):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO messages(message_id, user_id, platform, conversation_id, text, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                message.message_id,
                message.user_id,
                message.platform,
                message.conversation_id,
                message.message_text,
                message.timestamp,
            ),
        )
        conn.commit()

        summary_text, s_type, urgency, intent = classify_summary(message)
        summary_id = f"s_{uuid.uuid4().hex[:12]}"
        summary = SummaryOut(
            summary_id=summary_id,
            message_id=message.message_id,
            summary=summary_text,
            type=s_type,
            intent=intent,
            urgency=urgency,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

        cur.execute(
            """
            INSERT OR REPLACE INTO summaries(summary_id, message_id, summary, type, intent, urgency, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                summary.summary_id,
                summary.message_id,
                summary.summary,
                summary.type,
                summary.intent,
                summary.urgency,
                summary.timestamp,
            ),
        )
        conn.commit()
        return summary
    finally:
        conn.close()


@app.post("/api/process_summary", response_model=TaskOut)
def api_process_summary(summary: SummaryIn):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT text, user_id FROM messages WHERE message_id = ?", (summary.message_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="message_id not found")
        message_text = row["text"]
        user_id = row["user_id"]

        task_summary, task_type, scheduled_for = infer_task(summary, user_id, message_text)
        task = TaskOut(
            task_id=f"t_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            task_summary=task_summary,
            task_type=task_type,
            scheduled_for=scheduled_for,
            status="created",
        )

        cur.execute(
            """
            INSERT OR REPLACE INTO tasks(task_id, user_id, task_summary, task_type, scheduled_for, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                task.task_id,
                task.user_id,
                task.task_summary,
                task.task_type,
                task.scheduled_for,
                task.status,
            ),
        )
        conn.commit()
        return task
    finally:
        conn.close()


@app.post("/api/feedback")
def api_feedback(feedback: FeedbackIn):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO feedback(summary_id, rating, comment, timestamp) VALUES (?, ?, ?, ?)
            """,
            (feedback.summary_id, feedback.rating, feedback.comment, feedback.timestamp),
        )
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


# Extra observability endpoints
@app.get("/api/stats")
def api_stats() -> Dict[str, Any]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM messages")
        messages = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM summaries")
        summaries = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM tasks")
        tasks = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM feedback")
        feedback = cur.fetchone()[0]
        return {
            "success": True,
            "counts": {"messages": messages, "summaries": summaries, "tasks": tasks, "feedback": feedback},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    finally:
        conn.close()


@app.get("/api/metrics")
def api_metrics() -> Dict[str, Any]:
    # Lightweight placeholder metrics
    return {
        "success": True,
        "metrics": {"uptime": "n/a", "requests": "n/a"},
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# Optional: Bridge endpoints (integrate Assistant-Live-Bridge modules if available)
BRIDGE_AVAILABLE = False
try:
    BRIDGE_DIR = os.path.join(os.path.dirname(REPO_ROOT), "Assistant-Live-Bridge")
    if os.path.isdir(BRIDGE_DIR):
        if BRIDGE_DIR not in sys.path:
            sys.path.append(BRIDGE_DIR)
        from smart_summarizer_api import get_summarizer_api
        from cognitive_agent_api import get_cognitive_agent_api
        BRIDGE_AVAILABLE = True
except Exception as e:
    logger.warning(f"Bridge integration not available: {e}")


class BridgeMessageIn(BaseModel):
    user_id: str
    platform: str
    message_text: str
    timestamp: str
    message_id: Optional[str] = None


class BridgeSummaryIn(BaseModel):
    summary_id: Optional[str] = None
    user_id: str
    platform: str
    summary: str
    intent: str
    urgency: str
    type: Optional[str] = None
    confidence: Optional[float] = None
    reasoning: Optional[list[str]] = None
    context_used: Optional[bool] = False
    original_message: Optional[str] = None


if BRIDGE_AVAILABLE:
    @app.get("/bridge/health")
    def bridge_health():
        try:
            summarizer_api = get_summarizer_api()
            cognitive_api = get_cognitive_agent_api()
            s = summarizer_api.health_check()
            c = cognitive_api.health_check()
            overall = "healthy"
            if s.get("overall_status") != "healthy" or c.get("overall_status") != "healthy":
                overall = "degraded"
            return {"overall_status": overall, "components": {"summarizer": s, "cognitive_agent": c}, "timestamp": datetime.utcnow().isoformat() + "Z"}
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Bridge health failed: {str(e)}")

    @app.post("/bridge/summarize")
    def bridge_summarize(message: BridgeMessageIn):
        summarizer_api = get_summarizer_api()
        result = summarizer_api.process_message(message.dict())
        return result

    @app.post("/bridge/process_summary")
    def bridge_process_summary(summary: BridgeSummaryIn):
        cognitive_api = get_cognitive_agent_api()
        result = cognitive_api.process_summary(summary.dict())
        return result

    @app.post("/bridge/pipeline")
    def bridge_pipeline(message: BridgeMessageIn):
        summarizer_api = get_summarizer_api()
        summary_result = summarizer_api.process_message(message.dict())
        if not summary_result.get("success"):
            return {"success": False, "error": f"Summarization failed: {summary_result.get('error')}", "step_failed": "summarize"}
        auto_task = summary_result.get("auto_task")
        if auto_task and auto_task.get("success"):
            task_result = auto_task
        else:
            cognitive_api = get_cognitive_agent_api()
            task_result = cognitive_api.process_summary({
                "summary_id": summary_result.get("summary_id"),
                "user_id": message.user_id,
                "platform": message.platform,
                "summary": summary_result.get("summary"),
                "intent": summary_result.get("intent"),
                "urgency": summary_result.get("urgency"),
                "type": summary_result.get("type"),
                "confidence": summary_result.get("confidence"),
                "reasoning": summary_result.get("reasoning"),
                "context_used": summary_result.get("context_used"),
                "original_message": message.message_text,
            })
        return {"success": True, "summary": summary_result, "task": task_result}

# Aliases for broader compatibility (no /api prefix)
app.add_api_route("/health", health, methods=["GET"]) 
app.add_api_route("/summarize", api_summarize, methods=["POST"]) 
app.add_api_route("/process_summary", api_process_summary, methods=["POST"]) 
app.add_api_route("/feedback", api_feedback, methods=["POST"]) 
app.add_api_route("/stats", api_stats, methods=["GET"]) 
app.add_api_route("/metrics", api_metrics, methods=["GET"]) 

# Versioned aliases (/v1/*)
app.add_api_route("/v1/health", health, methods=["GET"]) 
app.add_api_route("/v1/summarize", api_summarize, methods=["POST"]) 
app.add_api_route("/v1/process_summary", api_process_summary, methods=["POST"]) 
app.add_api_route("/v1/feedback", api_feedback, methods=["POST"]) 
app.add_api_route("/v1/stats", api_stats, methods=["GET"]) 
app.add_api_route("/v1/metrics", api_metrics, methods=["GET"])