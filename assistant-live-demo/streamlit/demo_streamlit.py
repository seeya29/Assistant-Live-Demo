import os
import sqlite3
from datetime import datetime
import uuid
import json

import requests
import pandas as pd
import streamlit as st

# -------------------------------------------------------------------
# Config
# -------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, "assistant_demo.db")
SAMPLES_PATH = os.path.join(REPO_ROOT, "data", "sample_messages.json")
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

st.set_page_config(page_title="Assistant Live Demo", page_icon="🧪", layout="wide")
st.title("Assistant Live Demo: Message → Summary → Task")
st.caption("Send a message, see its summary and task, post feedback, and browse multiple samples.")

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def conn_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_table_df(name: str) -> pd.DataFrame:
    try:
        with conn_db() as c:
            df = pd.read_sql_query(f"SELECT * FROM {name}", c)
        return df
    except Exception:
        return pd.DataFrame()


def api_post(path: str, payload: dict, timeout: int = 20):
    url = f"{API_BASE}{path}"
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        return True, r.json()
    except requests.exceptions.HTTPError as e:
        body = e.response.text if e.response is not None else ""
        return False, f"HTTP {e.response.status_code if e.response else ''}: {body}"
    except requests.exceptions.RequestException as e:
        return False, f"Network error: {e}"


def now_iso():
    return datetime.utcnow().isoformat() + "Z"


def load_samples() -> list[dict]:
    try:
        with open(SAMPLES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list) and data:
                return data
    except Exception:
        pass
    # Fallback defaults
    return [
        {"user_id": "u1", "platform": "whatsapp", "conversation_id": "conv001", "message_id": "m1", "message_text": "Hey, did the report get done?", "timestamp": "2025-09-01T10:00:00Z"},
        {"user_id": "u2", "platform": "email",     "conversation_id": "conv002", "message_id": "m2", "message_text": "Can we reschedule the review to next Monday?", "timestamp": "2025-09-01T11:00:00Z"},
        {"user_id": "u3", "platform": "instagram", "conversation_id": "conv003", "message_id": "m3", "message_text": "Are you free to collab next week?", "timestamp": "2025-09-01T12:00:00Z"},
        {"user_id": "u4", "platform": "whatsapp",  "conversation_id": "conv004", "message_id": "m4", "message_text": "URGENT: Server is down, need help ASAP.", "timestamp": "2025-09-01T13:00:00Z"},
        {"user_id": "u5", "platform": "email",     "conversation_id": "conv005", "message_id": "m5", "message_text": "Reminder: invoice due by Friday.", "timestamp": "2025-09-01T14:00:00Z"},
    ]


def samples_by_platform(samples: list[dict]) -> dict[str, list[dict]]:
    d: dict[str, list[dict]] = {}
    for s in samples:
        d.setdefault(s.get("platform", "unknown"), []).append(s)
    return d


# Load samples once
SAMPLES = load_samples()
SAMPLES_IDX = {s.get("message_id"): s for s in SAMPLES}
SAMPLES_BY_PLAT = samples_by_platform(SAMPLES)
ALL_PLATFORMS = sorted(list({s.get("platform") for s in SAMPLES})) or ["whatsapp", "instagram", "email"]

# -------------------------------------------------------------------
# Session state defaults
# -------------------------------------------------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = "demo_user"
if "platform" not in st.session_state:
    st.session_state.platform = ALL_PLATFORMS[0]
if "message_text" not in st.session_state:
    # initialize with first sample of first platform
    first_plat = st.session_state.platform
    first_msg = (SAMPLES_BY_PLAT.get(first_plat) or SAMPLES)[0]
    st.session_state.message_text = first_msg.get("message_text", "")
if "sample_choice" not in st.session_state:
    st.session_state.sample_choice = (SAMPLES_BY_PLAT.get(st.session_state.platform) or SAMPLES)[0].get("message_id")

# -------------------------------------------------------------------
# Sample Controls (outside of the form to allow callbacks)
# -------------------------------------------------------------------
st.subheader("Pick Platform & Sample")
col_plat, col_sample = st.columns([1, 2])
with col_plat:
    # Changing platform selects first sample of that platform and auto-fills message
    def _on_platform_change():
        st.session_state.platform = st.session_state._platform_ui
        plat_samples = SAMPLES_BY_PLAT.get(st.session_state.platform) or []
        if plat_samples:
            st.session_state.sample_choice = plat_samples[0].get("message_id")
            st.session_state.message_text = plat_samples[0].get("message_text", "")

    st.selectbox(
        "Platform",
        options=ALL_PLATFORMS,
        key="_platform_ui",
        index=ALL_PLATFORMS.index(st.session_state.platform),
        on_change=_on_platform_change,
    )

with col_sample:
    plat_samples = SAMPLES_BY_PLAT.get(st.session_state.platform) or []
    if not plat_samples:
        st.info("No predefined samples for this platform. Add to data/sample_messages.json.")
    else:
        # Build labels and mapping
        labels = [f"{i}. {s['message_text'][:70]}{'…' if len(s['message_text'])>70 else ''}" for i, s in enumerate(plat_samples)]
        # selectbox with callback to update message_text
        def _on_sample_pick():
            idx = st.session_state._sample_pick_index
            if 0 <= idx < len(plat_samples):
                chosen = plat_samples[idx]
                st.session_state.sample_choice = chosen.get("message_id")
                st.session_state.message_text = chosen.get("message_text", "")
        st.selectbox(
            "Sample for platform",
            options=list(range(len(plat_samples))),
            format_func=lambda i: labels[i],
            key="_sample_pick_index",
            index=0 if st.session_state.sample_choice not in [p["message_id"] for p in plat_samples] else [p["message_id"] for p in plat_samples].index(st.session_state.sample_choice),
            on_change=_on_sample_pick,
        )

st.divider()

# -------------------------------------------------------------------
# Message Form (NO callbacks inside the form; must include submit button)
# -------------------------------------------------------------------
st.subheader("Send a Message")
with st.form("send_form", clear_on_submit=False):
    c1, c2 = st.columns([1, 1])
    with c1:
        st.text_input("User ID", key="user_id")
    with c2:
        st.text_input("Platform (from picker above)", value=st.session_state.platform, disabled=True)

    st.text_area("Message Text", key="message_text", height=120)

    submitted = st.form_submit_button("Send")

if submitted:
    if not st.session_state.message_text.strip():
        st.error("Message text cannot be empty")
    else:
        message_payload = {
            "user_id": st.session_state.user_id,
            "platform": st.session_state.platform,
            "conversation_id": f"conv_{st.session_state.user_id}",
            "message_id": f"m_{uuid.uuid4().hex[:10]}",
            "message_text": st.session_state.message_text.strip(),
            "timestamp": now_iso(),
        }
        with st.spinner("Posting to /api/summarize..."):
            ok, resp = api_post("/api/summarize", message_payload)
        if not ok:
            st.error(f"Summarize failed: {resp}")
        else:
            summary = resp
            rc1, rc2 = st.columns(2)
            with rc1:
                st.success("Summary created")
                st.markdown("#### Summary")
                st.json(summary, expanded=False)
            # Build summary.json for process_summary
            summary_payload = {
                "summary_id": summary["summary_id"],
                "message_id": summary["message_id"],
                "summary": summary["summary"],
                "type": summary["type"],
                "intent": summary["intent"],
                "urgency": summary["urgency"],
                "timestamp": summary["timestamp"],
            }
            with st.spinner("Posting to /api/process_summary..."):
                ok2, task_resp = api_post("/api/process_summary", summary_payload)
            with rc2:
                if not ok2:
                    st.error(f"Process summary failed: {task_resp}")
                else:
                    st.success("Task created")
                    st.markdown("#### Task")
                    st.json(task_resp, expanded=False)

st.divider()

# -------------------------------------------------------------------
# Live Database (Tabs)
# -------------------------------------------------------------------
st.subheader("Live Database")
refresh = st.button("Refresh Tables", help="Reload data from SQLite")

msgs = get_table_df("messages")
sums = get_table_df("summaries")
tasks = get_table_df("tasks")

msg_tab, sum_tab, task_tab = st.tabs(["Messages", "Summaries", "Tasks"])

with msg_tab:
    if msgs.empty:
        st.info("No messages yet")
    else:
        st.dataframe(msgs, use_container_width=True, hide_index=True, height=350)

with sum_tab:
    if sums.empty:
        st.info("No summaries yet")
    else:
        display_cols = [c for c in ["summary_id", "message_id", "summary", "type", "intent", "urgency", "timestamp"] if c in sums.columns]
        st.dataframe(sums[display_cols], use_container_width=True, hide_index=True, height=350)
        st.markdown("---")
        st.markdown("#### Feedback Actions")
        st.caption("Post Up/Down feedback for any summary")
        for _, row in sums.iterrows():
            container = st.container(border=True)
            with container:
                a, b, c = st.columns([0.7, 0.15, 0.15])
                with a:
                    st.markdown(f"**{row['summary_id']}**: {row['summary']}")
                    st.caption(f"Type: {row['type']} | Intent: {row['intent']} | Urgency: {row['urgency']}")
                with b:
                    if st.button("👍 Up", key=f"up_{row['summary_id']}"):
                        fb = {"summary_id": row["summary_id"], "rating": "up", "timestamp": now_iso()}
                        ok, resp = api_post("/api/feedback", fb)
                        if ok:
                            st.success("Recorded")
                        else:
                            st.error(resp)
                with c:
                    if st.button("👎 Down", key=f"down_{row['summary_id']}"):
                        fb = {"summary_id": row["summary_id"], "rating": "down", "timestamp": now_iso()}
                        ok, resp = api_post("/api/feedback", fb)
                        if ok:
                            st.success("Recorded")
                        else:
                            st.error(resp)

with task_tab:
    if tasks.empty:
        st.info("No tasks yet")
    else:
        st.dataframe(tasks, use_container_width=True, hide_index=True, height=350)

# Footer
st.markdown("---")
st.caption(f"DB: {DB_PATH} | API: {API_BASE} | Samples: {SAMPLES_PATH}")
