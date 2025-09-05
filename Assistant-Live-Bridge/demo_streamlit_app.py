"""
Demo Streamlit App - Simplified dashboard for the integrated SmartBrief v3 + Daily Cognitive Agent system.
This demonstrates the end-to-end pipeline from message processing to task creation.
"""

import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests
import os
from typing import Dict, List, Any

# Page configuration
st.set_page_config(
    page_title="SmartBrief v3 + Cognitive Agent Demo",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 0.5rem 0;
    }
    .success-card {
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
    }
    .warning-card {
        background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
    }
    .error-card {
        background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Configuration
API_BASE_URL = os.getenv('API_BASE_URL', 'http://127.0.0.1:8000')

# Initialize session state
if 'demo_messages' not in st.session_state:
    st.session_state.demo_messages = []
if 'processed_summaries' not in st.session_state:
    st.session_state.processed_summaries = []
if 'created_tasks' not in st.session_state:
    st.session_state.created_tasks = []
if 'api_responses' not in st.session_state:
    st.session_state.api_responses = []

# Sample demo messages
DEMO_MESSAGES = [
    {
        "user_id": "alice_work",
        "platform": "email",
        "message_text": "Hi team, we need to schedule the quarterly review meeting for next week. Please share availability for Tue/Wed afternoon.",
        "timestamp": "2025-08-07T09:00:00Z",
        "message_id": "msg_001"
    },
    {
        "user_id": "bob_personal",
        "platform": "whatsapp",
        "message_text": "Hey! The concert tickets go on sale tomorrow at 10am. Don't forget to get them!",
        "timestamp": "2025-08-07T14:30:00Z",
        "message_id": "msg_002"
    },
    {
        "user_id": "customer_support",
        "platform": "slack",
        "message_text": "URGENT: The payment system is down and customers cannot complete purchases. Need immediate attention!",
        "timestamp": "2025-08-07T11:15:00Z",
        "message_id": "msg_003"
    },
    {
        "user_id": "project_manager",
        "platform": "teams",
        "message_text": "Can we schedule a quick standup tomorrow at 10 AM? Need to discuss sprint planning and blockers.",
        "timestamp": "2025-08-07T17:10:00Z",
        "message_id": "msg_004"
    },
    {
        "user_id": "ops_oncall",
        "platform": "slack",
        "message_text": "We need to schedule maintenance tonight between 11pm and 1am. Notify stakeholders.",
        "timestamp": "2025-08-07T18:05:00Z",
        "message_id": "msg_005"
    },
    {
        "user_id": "sales_team",
        "platform": "email",
        "message_text": "Please prepare the Q3 pipeline deck and send by Friday EOD.",
        "timestamp": "2025-08-07T09:45:00Z",
        "message_id": "msg_006"
    },
    {
        "user_id": "product_mgr",
        "platform": "whatsapp",
        "message_text": "Let's sync in 2 hours about the launch checklist.",
        "timestamp": "2025-08-07T10:00:00Z",
        "message_id": "msg_007"
    },
    {
        "user_id": "design_lead",
        "platform": "teams",
        "message_text": "Review new mockups next Tuesday at 3 PM.",
        "timestamp": "2025-08-07T12:00:00Z",
        "message_id": "msg_008"
    },
    {
        "user_id": "marketing",
        "platform": "instagram",
        "message_text": "FYI: Campaign kickoff delayed; reschedule the briefing call to tomorrow morning.",
        "timestamp": "2025-08-07T08:30:00Z",
        "message_id": "msg_009"
    },
    {
        "user_id": "qa_lead",
        "platform": "telegram",
        "message_text": "Smoke tests failed on staging. Please investigate ASAP.",
        "timestamp": "2025-08-07T13:20:00Z",
        "message_id": "msg_010"
    },
    {
        "user_id": "engineering",
        "platform": "email",
        "message_text": "Can we do a code freeze meeting next Friday at 4pm?",
        "timestamp": "2025-08-07T16:40:00Z",
        "message_id": "msg_011"
    },
    {
        "user_id": "support_mgr",
        "platform": "slack",
        "message_text": "Customer escalation pending; schedule a follow-up call today at 5pm.",
        "timestamp": "2025-08-07T10:50:00Z",
        "message_id": "msg_012"
    }
]

def call_api_endpoint(endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Call API endpoint with error handling."""
    try:
        api_key = os.getenv('API_KEY')
        headers = {'x-api-key': api_key} if api_key else {}
        response = requests.post(f"{API_BASE_URL}/{endpoint}", json=data, headers=headers, timeout=30)
        response.raise_for_status()
        return {'success': True, 'data': response.json()}
    except requests.exceptions.ConnectionError:
        return {'success': False, 'error': f'Could not connect to API at {API_BASE_URL}. Make sure the FastAPI server is running.'}
    except requests.exceptions.Timeout:
        return {'success': False, 'error': 'API request timed out'}
    except requests.exceptions.HTTPError as e:
        try:
            body = e.response.text
        except Exception:
            body = ''
        return {'success': False, 'error': f'HTTP error: {e.response.status_code} - {body}'}
    except Exception as e:
        return {'success': False, 'error': f'Unexpected error: {str(e)}'}

def simulate_api_response(endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate API responses when actual API is not available."""
    if endpoint == 'summarize':
        return {
            'success': True,
            'data': {
                'summary_id': f"sum_{datetime.now().strftime('%H%M%S')}",
                'summary': data['message_text'][:100] + '...' if len(data['message_text']) > 100 else data['message_text'],
                'intent': 'meeting' if 'meeting' in data['message_text'].lower() else 'task',
                'urgency': 'high' if 'urgent' in data['message_text'].lower() else 'medium',
                'type': 'meeting' if 'meeting' in data['message_text'].lower() else 'action_required',
                'confidence': 0.85,
                'reasoning': ['Keyword analysis', 'Context evaluation'],
                'context_used': True
            }
        }
    elif endpoint == 'process_summary':
        return {
            'success': True,
            'data': {
                'task_id': f"task_{datetime.now().strftime('%H%M%S')}",
                'task_summary': data.get('summary', 'Process task'),
                'status': 'pending',
                'priority': data.get('urgency', 'medium'),
                'recommendations': [
                    {'action': 'calendar_block', 'description': 'Block time in calendar', 'priority': 'high'},
                    {'action': 'set_reminder', 'description': 'Set reminder notification', 'priority': 'medium'}
                ]
            }
        }
    elif endpoint == 'feedback':
        return {'success': True, 'data': {'message': 'Feedback recorded successfully'}}
    
    return {'success': False, 'error': 'Unknown endpoint'}

# Sidebar
st.sidebar.title("🎛️ Demo Controls")

# API Connection Status
st.sidebar.subheader("🔗 API Status")
use_live_api = st.sidebar.checkbox("Use Live API", value=True, help="Uncheck to use simulated responses")

if use_live_api:
    # Test API connection (try /health then /v1/health)
    connected = False
    try:
        resp = requests.get(f"{API_BASE_URL}/health", timeout=5)
        connected = (resp.status_code == 200)
        if not connected:
            resp2 = requests.get(f"{API_BASE_URL}/v1/health", timeout=5)
            connected = (resp2.status_code == 200)
    except Exception:
        connected = False

    if connected:
        st.sidebar.success("✅ API Connected")
    else:
        st.sidebar.error("❌ API Offline — switched to Simulated Mode")
        use_live_api = False
else:
    st.sidebar.info("🔄 Using Simulated Mode")

st.sidebar.markdown("---")

# Demo Data Controls
st.sidebar.subheader("📊 Demo Data")

if st.sidebar.button("Load Demo Messages"):
    st.session_state.demo_messages = DEMO_MESSAGES.copy()
    st.sidebar.success(f"Loaded {len(DEMO_MESSAGES)} demo messages")

if st.sidebar.button("Clear All Data"):
    st.session_state.demo_messages = []
    st.session_state.processed_summaries = []
    st.session_state.created_tasks = []
    st.session_state.api_responses = []
    st.sidebar.success("All data cleared")

st.sidebar.markdown("---")

# Custom Message Input
st.sidebar.subheader("📝 Add Custom Message")
with st.sidebar.form("custom_message"):
    user_id = st.text_input("User ID", value="demo_user")
    platform = st.selectbox("Platform", ["email", "whatsapp", "slack", "teams", "instagram"])
    message_text = st.text_area("Message Text", height=100)
    
    if st.form_submit_button("Add Message"):
        if message_text.strip():
            custom_message = {
                "user_id": user_id,
                "platform": platform,
                "message_text": message_text,
                "timestamp": datetime.now().isoformat(),
                "message_id": f"custom_{len(st.session_state.demo_messages)}"
            }
            st.session_state.demo_messages.append(custom_message)
            st.sidebar.success("Custom message added!")

# Main Content
st.title("🧠 SmartBrief v3 + Cognitive Agent Demo")
st.markdown("**End-to-end pipeline demonstration: Message → Summary → Task**")

# Helper to ensure a robust payload for task creation

def build_summary_payload(summary: Dict[str, Any], fallback_msg: Dict[str, Any] = None) -> Dict[str, Any]:
    payload = dict(summary)
    # Ensure mandatory fields expected by API
    if 'user_id' not in payload or not payload.get('user_id'):
        if fallback_msg:
            payload['user_id'] = fallback_msg.get('user_id')
        else:
            payload['user_id'] = 'demo_user'
    if 'platform' not in payload or not payload.get('platform'):
        if fallback_msg:
            payload['platform'] = fallback_msg.get('platform', 'email')
        else:
            payload['platform'] = 'email'
    # Ensure original_message is a string
    orig = payload.get('original_message')
    if isinstance(orig, dict):
        payload['original_message'] = orig.get('message_text')
    elif not isinstance(orig, str):
        if fallback_msg:
            payload['original_message'] = fallback_msg.get('message_text')
        else:
            payload['original_message'] = payload.get('summary')
    # Ensure intent/urgency exist
    payload['intent'] = payload.get('intent', 'info')
    payload['urgency'] = payload.get('urgency', 'medium')
    # Type can be missing; API can infer, but include if present
    return payload

# Navigation tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📥 Messages", "📝 Summaries", "✅ Tasks", "📊 Analytics", "🔧 API Testing"])

# Tab 1: Messages
with tab1:
    st.header("📥 Incoming Messages")
    
    if not st.session_state.demo_messages:
        st.info("No messages loaded. Use the sidebar to load demo messages or add custom ones.")
    else:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader(f"Messages ({len(st.session_state.demo_messages)})")
            
            for i, msg in enumerate(st.session_state.demo_messages):
                with st.expander(f"#{i+1} - {msg['platform'].upper()} | {msg['user_id']}", expanded=False):
                    st.markdown(f"**Platform:** {msg['platform']}")
                    st.markdown(f"**User:** {msg['user_id']}")
                    st.markdown(f"**Timestamp:** {msg['timestamp']}")
                    st.markdown(f"**Message:**")
                    st.text(msg['message_text'])
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button(f"📝 Summarize", key=f"summarize_{i}"):
                            with st.spinner("Processing..."):
                                if use_live_api:
                                    result = call_api_endpoint('summarize', msg)
                                else:
                                    result = simulate_api_response('summarize', msg)
                                
                                if result['success']:
                                    summary_data = result['data']
                                    # Ensure required fields are present for task creation via live API
                                    summary_data['user_id'] = msg.get('user_id')
                                    summary_data['platform'] = msg.get('platform')
                                    summary_data['message_id'] = msg.get('message_id')
                                    # Pass only the message text string for original_message (not the whole dict)
                                    summary_data['original_message'] = msg.get('message_text')
                                    st.session_state.processed_summaries.append(summary_data)
                                    st.session_state.api_responses.append({
                                        'endpoint': 'summarize',
                                        'request': msg,
                                        'response': result,
                                        'timestamp': datetime.now().isoformat()
                                    })
                                    st.success("Summary created!")
                                else:
                                    st.error(f"Error: {result['error']}")
                    
                    with col_b:
                        if st.button(f"🚀 Full Pipeline", key=f"pipeline_{i}"):
                            with st.spinner("Running full pipeline..."):
                                # Step 1: Summarize
                                if use_live_api:
                                    summary_result = call_api_endpoint('summarize', msg)
                                else:
                                    summary_result = simulate_api_response('summarize', msg)
                                
                                if summary_result['success']:
                                    summary_data = summary_result['data']
                                    # Ensure required fields are present for task creation via live API
                                    summary_data['user_id'] = msg.get('user_id')
                                    summary_data['platform'] = msg.get('platform')
                                    summary_data['message_id'] = msg.get('message_id')
                                    # Pass only the message text string for original_message (not the whole dict)
                                    summary_data['original_message'] = msg.get('message_text')
                                    st.session_state.processed_summaries.append(summary_data)
                                    
                                    # Step 2: Create Task
                                    if use_live_api:
                                        task_result = call_api_endpoint('process_summary', build_summary_payload(summary_data, msg))
                                    else:
                                        task_result = simulate_api_response('process_summary', summary_data)
                                    
                                    if task_result['success']:
                                        task_data = task_result['data']
                                        task_data['original_summary'] = summary_data
                                        # Enrich with user/platform for filtering/display
                                        task_data['user_id'] = summary_data.get('user_id')
                                        task_data['platform'] = summary_data.get('platform')
                                        st.session_state.created_tasks.append(task_data)
                                        
                                        st.success("✅ Full pipeline completed!")
                                        st.info(f"Created task: {task_data['task_id']}")
                                    else:
                                        st.error(f"Task creation failed: {task_result['error']}")
                                else:
                                    st.error(f"Summarization failed: {summary_result['error']}")
        
        with col2:
            st.subheader("📊 Quick Stats")
            
            # Platform distribution
            platforms = [msg['platform'] for msg in st.session_state.demo_messages]
            platform_counts = pd.Series(platforms).value_counts()
            
            st.markdown("**Platform Distribution:**")
            for platform, count in platform_counts.items():
                st.markdown(f"• {platform}: {count}")
            
            st.markdown("---")
            
            # Processing stats
            st.markdown("**Processing Status:**")
            st.markdown(f"• Total Messages: {len(st.session_state.demo_messages)}")
            st.markdown(f"• Processed Summaries: {len(st.session_state.processed_summaries)}")
            st.markdown(f"• Created Tasks: {len(st.session_state.created_tasks)}")

# Tab 2: Summaries
with tab2:
    st.header("📝 Processed Summaries")
    
    if not st.session_state.processed_summaries:
        st.info("No summaries yet. Process some messages first.")
    else:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            for i, summary in enumerate(st.session_state.processed_summaries):
                with st.container():
                    st.markdown(f"### Summary #{i+1}")
                    
                    # Summary details
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown(f"**Summary:** {summary['summary']}")
                        st.markdown(f"**Intent:** {summary['intent']}")
                        st.markdown(f"**Type:** {summary['type']}")
                    with col_b:
                        st.markdown(f"**Urgency:** {summary['urgency']}")
                        st.markdown(f"**Confidence:** {summary['confidence']:.2f}")
                        st.markdown(f"**Context Used:** {'Yes' if summary.get('context_used') else 'No'}")
                    
                    # Reasoning
                    if 'reasoning' in summary:
                        with st.expander("🧠 Reasoning"):
                            for reason in summary['reasoning']:
                                st.markdown(f"• {reason}")
                    
                    # Feedback section
                    col_c, col_d, col_e = st.columns(3)
                    with col_c:
                        if st.button("👍 Good", key=f"upvote_{i}"):
                            feedback_data = {
                                'summary_id': summary.get('summary_id', f'sum_{i}'),
                                'feedback': 'upvote',
                                'comment': 'User approved summary'
                            }
                            if use_live_api:
                                result = call_api_endpoint('feedback', feedback_data)
                            else:
                                result = simulate_api_response('feedback', feedback_data)
                            
                            if result['success']:
                                st.success("👍 Feedback recorded!")
                            else:
                                st.error(f"Error: {result['error']}")
                    
                    with col_d:
                        if st.button("👎 Poor", key=f"downvote_{i}"):
                            feedback_data = {
                                'summary_id': summary.get('summary_id', f'sum_{i}'),
                                'feedback': 'downvote',
                                'comment': 'User rejected summary'
                            }
                            if use_live_api:
                                result = call_api_endpoint('feedback', feedback_data)
                            else:
                                result = simulate_api_response('feedback', feedback_data)
                            
                            if result['success']:
                                st.success("👎 Feedback recorded!")
                            else:
                                st.error(f"Error: {result['error']}")
                    
                    with col_e:
                        if st.button("➡️ Create Task", key=f"create_task_{i}"):
                            with st.spinner("Creating task..."):
                                if use_live_api:
                                    result = call_api_endpoint('process_summary', build_summary_payload(summary))
                                else:
                                    result = simulate_api_response('process_summary', summary)
                                
                                if result['success']:
                                    task_data = result['data']
                                    task_data['original_summary'] = summary
                                    # Enrich with user/platform for filtering/display
                                    task_data['user_id'] = summary.get('user_id')
                                    task_data['platform'] = summary.get('platform')
                                    st.session_state.created_tasks.append(task_data)
                                    st.success("✅ Task created!")
                                else:
                                    st.error(f"Error: {result['error']}")
                    
                    st.markdown("---")
        
        with col2:
            st.subheader("📈 Summary Analytics")
            
            # Intent distribution
            intents = [s['intent'] for s in st.session_state.processed_summaries]
            intent_counts = pd.Series(intents).value_counts()
            
            fig_pie = px.pie(values=intent_counts.values, names=intent_counts.index, title="Intent Distribution")
            st.plotly_chart(fig_pie, use_container_width=True)
            
            # Urgency distribution
            urgencies = [s['urgency'] for s in st.session_state.processed_summaries]
            urgency_counts = pd.Series(urgencies).value_counts()
            
            fig_bar = px.bar(x=urgency_counts.index, y=urgency_counts.values, title="Urgency Levels")
            st.plotly_chart(fig_bar, use_container_width=True)

# Tab 3: Tasks
with tab3:
    st.header("✅ Created Tasks")
    
    if not st.session_state.created_tasks:
        st.info("No tasks yet. Process summaries to create tasks.")
    else:
        # Task filters
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.selectbox("Filter by Status", ["All", "pending", "completed", "in_progress"])
        with col2:
            priority_filter = st.selectbox("Filter by Priority", ["All", "high", "medium", "low"])
        with col3:
            user_filter = st.selectbox("Filter by User", ["All"] + sorted(list(set([t.get('user_id', 'Unknown') for t in st.session_state.created_tasks]))))
        
        # Filter tasks
        filtered_tasks = st.session_state.created_tasks
        if status_filter != "All":
            filtered_tasks = [t for t in filtered_tasks if t.get('status') == status_filter]
        if priority_filter != "All":
            filtered_tasks = [t for t in filtered_tasks if t.get('priority') == priority_filter]
        if user_filter != "All":
            filtered_tasks = [t for t in filtered_tasks if t.get('user_id') == user_filter]
        
        st.markdown(f"**Showing {len(filtered_tasks)} of {len(st.session_state.created_tasks)} tasks**")
        
        # Task display
        for i, task in enumerate(filtered_tasks):
            with st.container():
                st.markdown(f"### Task #{i+1}: {task.get('task_id', 'Unknown ID')}")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown(f"**Summary:** {task.get('task_summary', 'No summary')}")
                    st.markdown(f"**Status:** {task.get('status', 'Unknown')}")
                    st.markdown(f"**Priority:** {task.get('priority', 'Unknown')}")
                
                with col_b:
                    st.markdown(f"**User:** {task.get('user_id', 'Unknown')}")
                    st.markdown(f"**Platform:** {task.get('platform', 'Unknown')}")
                    st.markdown(f"**Created:** {task.get('created_at', 'Unknown')}")
                
                # Recommendations
                if 'recommendations' in task and task['recommendations']:
                    with st.expander("💡 Recommendations"):
                        for rec in task['recommendations']:
                            st.markdown(f"• **{rec['action']}**: {rec['description']} (Priority: {rec['priority']})")
                
                st.markdown("---")

# Tab 4: Analytics
with tab4:
    st.header("📊 System Analytics")
    
    if not st.session_state.demo_messages:
        st.info("No data for analytics. Load demo messages and process them first.")
    else:
        # Overall metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("""
            <div class="metric-card">
                <h3>📥 Total Messages</h3>
                <h2>{}</h2>
            </div>
            """.format(len(st.session_state.demo_messages)), unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="metric-card">
                <h3>📝 Summaries</h3>
                <h2>{}</h2>
            </div>
            """.format(len(st.session_state.processed_summaries)), unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class="metric-card">
                <h3>✅ Tasks</h3>
                <h2>{}</h2>
            </div>
            """.format(len(st.session_state.created_tasks)), unsafe_allow_html=True)
        
        with col4:
            processing_rate = (len(st.session_state.processed_summaries) / len(st.session_state.demo_messages) * 100) if st.session_state.demo_messages else 0
            st.markdown("""
            <div class="metric-card">
                <h3>📈 Processing Rate</h3>
                <h2>{:.1f}%</h2>
            </div>
            """.format(processing_rate), unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Charts
        if st.session_state.processed_summaries:
            col1, col2 = st.columns(2)
            
            with col1:
                # Platform vs Urgency
                data = []
                for summary in st.session_state.processed_summaries:
                    orig_msg = summary.get('original_message')
                    platform_val = summary.get('platform', 'Unknown')
                    if isinstance(orig_msg, dict):
                        platform_val = orig_msg.get('platform', platform_val)
                    data.append({
                        'platform': platform_val,
                        'urgency': summary.get('urgency', 'Unknown'),
                        'intent': summary.get('intent', 'Unknown')
                    })
                
                df = pd.DataFrame(data)
                
                if not df.empty:
                    fig_heatmap = px.density_heatmap(
                        df, x='platform', y='urgency', 
                        title="Platform vs Urgency Distribution"
                    )
                    st.plotly_chart(fig_heatmap, use_container_width=True)
            
            with col2:
                # Confidence scores over time
                confidences = [s.get('confidence', 0) for s in st.session_state.processed_summaries]
                indices = list(range(1, len(confidences) + 1))
                
                fig_line = px.line(
                    x=indices, y=confidences,
                    title="Confidence Scores Over Time",
                    labels={'x': 'Message Number', 'y': 'Confidence'}
                )
                st.plotly_chart(fig_line, use_container_width=True)

# Tab 5: API Testing
with tab5:
    st.header("🔧 API Testing")
    
    st.markdown(f"**API Base URL:** `{API_BASE_URL}`")
    
    # API endpoint testing
    endpoint = st.selectbox("Select Endpoint", ["summarize", "process_summary", "feedback"])
    
    if endpoint == "summarize":
        st.subheader("POST /summarize")
        with st.form("test_summarize"):
            user_id = st.text_input("User ID", value="test_user")
            platform = st.selectbox("Platform", ["email", "whatsapp", "slack", "teams"])
            message_text = st.text_area("Message Text", value="Can we schedule a meeting for tomorrow at 2pm?")
            timestamp = st.text_input("Timestamp", value=datetime.now().isoformat())
            
            if st.form_submit_button("Test Endpoint"):
                test_data = {
                    "user_id": user_id,
                    "platform": platform,
                    "message_text": message_text,
                    "timestamp": timestamp,
                    "message_id": f"test_{datetime.now().strftime('%H%M%S')}"
                }
                
                with st.spinner("Testing..."):
                    if use_live_api:
                        result = call_api_endpoint('summarize', test_data)
                    else:
                        result = simulate_api_response('summarize', test_data)
                    
                    if result['success']:
                        st.success("✅ API call successful!")
                        st.json(result['data'])
                    else:
                        st.error(f"❌ API call failed: {result['error']}")
    
    elif endpoint == "process_summary":
        st.subheader("POST /process_summary")
        with st.form("test_process_summary"):
            summary = st.text_input("Summary", value="Meeting request for tomorrow")
            intent = st.selectbox("Intent", ["meeting", "task", "question", "urgent"])
            urgency = st.selectbox("Urgency", ["low", "medium", "high", "critical"])
            
            if st.form_submit_button("Test Endpoint"):
                test_data = {
                    "summary": summary,
                    "intent": intent,
                    "urgency": urgency,
                    "user_id": "test_user",
                    "platform": "email"
                }
                
                with st.spinner("Testing..."):
                    if use_live_api:
                        result = call_api_endpoint('process_summary', test_data)
                    else:
                        result = simulate_api_response('process_summary', test_data)
                    
                    if result['success']:
                        st.success("✅ API call successful!")
                        st.json(result['data'])
                    else:
                        st.error(f"❌ API call failed: {result['error']}")
    
    elif endpoint == "feedback":
        st.subheader("POST /feedback")
        with st.form("test_feedback"):
            summary_id = st.text_input("Summary ID", value="test_summary_123")
            feedback = st.selectbox("Feedback", ["upvote", "downvote"])
            comment = st.text_area("Comment (optional)", value="")
            
            if st.form_submit_button("Test Endpoint"):
                test_data = {
                    "summary_id": summary_id,
                    "feedback": feedback,
                    "comment": comment
                }
                
                with st.spinner("Testing..."):
                    if use_live_api:
                        result = call_api_endpoint('feedback', test_data)
                    else:
                        result = simulate_api_response('feedback', test_data)
                    
                    if result['success']:
                        st.success("✅ API call successful!")
                        st.json(result['data'])
                    else:
                        st.error(f"❌ API call failed: {result['error']}")
    
    st.markdown("---")
    
    # Recent API responses
    if st.session_state.api_responses:
        st.subheader("📋 Recent API Responses")
        for i, response in enumerate(st.session_state.api_responses[-5:]):  # Show last 5
            with st.expander(f"Response #{len(st.session_state.api_responses) - i}: {response['endpoint']}"):
                st.markdown(f"**Timestamp:** {response['timestamp']}")
                st.markdown("**Request:**")
                st.json(response['request'])
                st.markdown("**Response:**")
                st.json(response['response'])

# Footer
st.markdown("---")
st.markdown("**SmartBrief v3 + Daily Cognitive Agent Integration Demo**")
st.markdown("This demo showcases the end-to-end pipeline from message processing to task creation.")