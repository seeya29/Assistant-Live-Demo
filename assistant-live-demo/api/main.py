import os
import sqlite3
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Paths
API_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(API_DIR)
DB_PATH = os.path.join(REPO_ROOT, "assistant_demo.db")

# FastAPI app
app = FastAPI(title="Assistant Live Demo API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    # Keep DB waits short so HTTP requests do not time out; return 503 quickly on lock
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


def classify_summary(msg: MessageIn) -> tuple[str, SummaryType, Urgency]:
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

    # naive schedule extraction: look for explicit ISO-like or simple hints
    scheduled_for = None
    # very light parsing: if "next" or weekday present, set 3 days from now; if "tomorrow" set 1 day
    now = datetime.utcnow()
    if "tomorrow" in text:
        scheduled_for = (now.replace(microsecond=0) + timedelta(days=1)).isoformat() + "Z"
    elif "next" in text or any(d in text for d in ["monday", "tuesday", "wednesday", "thursday", "friday"]):
        scheduled_for = (now.replace(microsecond=0) + timedelta(days=3)).isoformat() + "Z"

    task_summary = summary.summary.replace("User ", "").strip()
    if not task_summary:
        task_summary = "Follow up"

    return task_summary, ttype, scheduled_for


# Routes
@app.on_event("startup")
def _startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.post("/api/summarize", response_model=SummaryOut)
def api_summarize(message: MessageIn):
    # Persist message
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
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=503, detail=f"Database error (messages): {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store message: {str(e)}")
    finally:
        conn.close()

    # Classify + build summary
    smry_text, smry_type, urgency, intent = classify_summary(message)
    summary_id = f"s_{uuid.uuid4().hex[:12]}"
    ts = datetime.utcnow().isoformat() + "Z"

    # Persist summary
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO summaries(summary_id, message_id, summary, type, intent, urgency, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (summary_id, message.message_id, smry_text, smry_type, intent, urgency, ts),
        )
        conn.commit()
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=503, detail=f"Database error (summaries): {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store summary: {str(e)}")
    finally:
        conn.close()

    return SummaryOut(
        summary_id=summary_id,
        message_id=message.message_id,
        summary=smry_text,
        type=smry_type,
        intent=intent,
        urgency=urgency,
        timestamp=ts,
    )


@app.post("/api/process_summary", response_model=TaskOut)
def api_process_summary(summary: SummaryIn):
    # Get message to infer user_id and original text
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT user_id, text FROM messages WHERE message_id = ?", (summary.message_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="message_id not found for summary")
        user_id = row["user_id"]
        message_text = row["text"]
    finally:
        conn.close()

    task_summary, task_type, scheduled_for = infer_task(summary, user_id, message_text)
    task_id = f"t_{uuid.uuid4().hex[:12]}"

    # Persist task
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO tasks(task_id, user_id, task_summary, task_type, scheduled_for, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (task_id, user_id, task_summary, task_type, scheduled_for, "pending"),
        )
        conn.commit()
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=503, detail=f"Database error (tasks): {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store task: {str(e)}")
    finally:
        conn.close()

    return TaskOut(
        task_id=task_id,
        user_id=user_id,
        task_summary=task_summary,
        task_type=task_type,
        scheduled_for=scheduled_for,
        status="pending",
    )


@app.post("/api/feedback")
def api_feedback(feedback: FeedbackIn):
    # ensure summary exists
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM summaries WHERE summary_id = ?", (feedback.summary_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="summary_id not found")
        cur.execute(
            """
            INSERT INTO feedback(summary_id, rating, comment, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (feedback.summary_id, feedback.rating, feedback.comment, feedback.timestamp),
        )
        conn.commit()
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=503, detail=f"Database error (feedback): {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store feedback: {str(e)}")
    finally:
        conn.close()
    return {"success": True, "summary_id": feedback.summary_id, "timestamp": feedback.timestamp}
