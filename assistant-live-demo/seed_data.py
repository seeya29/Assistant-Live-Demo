#!/usr/bin/env python3
"""
Data seeding script for Assistant Live Demo
Populates the database with sample messages, summaries, tasks, and feedback for testing.
"""

import os
import sys
import json
import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict

# Add the project root to Python path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
SAMPLE_DATA_PATH = os.path.join(SCRIPT_DIR, "data", "sample_messages.json")


def load_sample_messages() -> List[Dict]:
    """Load sample messages from JSON file"""
    try:
        with open(SAMPLE_DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading sample messages: {e}")
        return []


def api_post(endpoint: str, payload: dict, timeout: int = 30) -> tuple[bool, dict]:
    """Make POST request to API"""
    url = f"{API_BASE}{endpoint}"
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        return True, response.json()
    except requests.exceptions.HTTPError as e:
        error_detail = e.response.text if e.response else str(e)
        print(f"HTTP Error {e.response.status_code if e.response else 'Unknown'}: {error_detail}")
        return False, {"error": error_detail}
    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")
        return False, {"error": str(e)}


def check_api_health() -> bool:
    """Check if API is running"""
    try:
        response = requests.get(f"{API_BASE}/api/health", timeout=10)
        return response.status_code == 200
    except:
        return False


def seed_sample_data():
    """Seed the database with sample data"""
    print("=== Assistant Live Demo - Data Seeding ===")
    
    # Check API health
    print("1. Checking API health...")
    if not check_api_health():
        print("❌ API is not running. Please start the API server first:")
        print("   uvicorn api.main:app --reload --port 8000")
        return False
    print("✅ API is running")
    
    # Load sample messages
    print("2. Loading sample messages...")
    messages = load_sample_messages()
    if not messages:
        print("❌ No sample messages found")
        return False
    print(f"✅ Loaded {len(messages)} sample messages")
    
    # Process each message through the full pipeline
    print("3. Processing messages through pipeline...")
    processed_count = 0
    summary_ids = []
    
    for i, message in enumerate(messages):
        print(f"   Processing message {i+1}/{len(messages)}: {message['message_text'][:50]}...")
        
        # Step 1: Summarize message
        success, summary_response = api_post("/api/summarize", message)
        if not success:
            print(f"   ❌ Failed to summarize message {i+1}")
            continue
        
        summary = summary_response
        summary_ids.append(summary['summary_id'])
        
        # Step 2: Create task from summary
        summary_payload = {
            "summary_id": summary["summary_id"],
            "message_id": summary["message_id"],
            "summary": summary["summary"],
            "type": summary["type"],
            "intent": summary["intent"],
            "urgency": summary["urgency"],
            "timestamp": summary["timestamp"],
        }
        
        success, task_response = api_post("/api/process_summary", summary_payload)
        if not success:
            print(f"   ❌ Failed to create task for message {i+1}")
            continue
        
        processed_count += 1
        print(f"   ✅ Created summary {summary['summary_id']} and task {task_response['task_id']}")
        
        # Small delay to avoid overwhelming the API
        time.sleep(0.1)
    
    print(f"✅ Successfully processed {processed_count}/{len(messages)} messages")
    
    # Add sample feedback
    print("4. Adding sample feedback...")
    feedback_data = [
        {"rating": "up", "comment": "Great summary!"},
        {"rating": "up", "comment": "Very accurate"},
        {"rating": "down", "comment": "Missed the urgency"},
        {"rating": "up", "comment": None},
        {"rating": "down", "comment": "Wrong intent classification"},
        {"rating": "up", "comment": "Perfect classification"},
    ]
    
    feedback_count = 0
    for i, feedback_template in enumerate(feedback_data):
        if i < len(summary_ids):
            feedback = {
                "summary_id": summary_ids[i],
                "rating": feedback_template["rating"],
                "comment": feedback_template["comment"],
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            success, response = api_post("/api/feedback", feedback)
            if success:
                feedback_count += 1
                print(f"   ✅ Added feedback for summary {summary_ids[i]}")
            else:
                print(f"   ❌ Failed to add feedback for summary {summary_ids[i]}")
    
    print(f"✅ Successfully added {feedback_count} feedback entries")
    
    # Print summary statistics
    print("\n=== Seeding Complete ===")
    print(f"📊 Statistics:")
    print(f"   Messages processed: {processed_count}")
    print(f"   Summaries created: {processed_count}")
    print(f"   Tasks created: {processed_count}")
    print(f"   Feedback entries: {feedback_count}")
    print(f"\n🔍 You can now:")
    print(f"   - View API stats: GET {API_BASE}/api/stats")
    print(f"   - Browse messages: GET {API_BASE}/api/messages")
    print(f"   - Browse summaries: GET {API_BASE}/api/summaries")
    print(f"   - Browse tasks: GET {API_BASE}/api/tasks")
    print(f"   - Run Streamlit: streamlit run streamlit/demo_streamlit.py")
    
    return True


if __name__ == "__main__":
    success = seed_sample_data()
    sys.exit(0 if success else 1)