#!/usr/bin/env python3
"""
End-to-End Flow Test Script
Demonstrates complete message → summary → task → feedback pipeline
"""

import os
import sys
import json
import time
import requests
from datetime import datetime
from typing import Dict, Any, List

# Configuration
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
TIMEOUT = 30

def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def print_step(step: int, description: str):
    """Print a step in the process"""
    print(f"\n[Step {step}] {description}")
    print("-" * 50)

def api_request(method: str, endpoint: str, payload: Dict = None) -> tuple[bool, Dict]:
    """Make API request with error handling"""
    url = f"{API_BASE}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=TIMEOUT)
        elif method == "POST":
            response = requests.post(url, json=payload, timeout=TIMEOUT)
        elif method == "PUT":
            response = requests.put(url, json=payload, timeout=TIMEOUT)
        else:
            return False, {"error": f"Unsupported method: {method}"}
        
        response.raise_for_status()
        return True, response.json()
    
    except requests.exceptions.HTTPError as e:
        error_detail = e.response.text if e.response else str(e)
        return False, {"error": f"HTTP {e.response.status_code}: {error_detail}"}
    except requests.exceptions.RequestException as e:
        return False, {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        return False, {"error": f"Unexpected error: {str(e)}"}

def test_api_health():
    """Test API health endpoint"""
    print_step(1, "Testing API Health")
    
    success, response = api_request("GET", "/api/health")
    
    if success:
        print("✅ API is healthy")
        print(f"   Status: {response.get('status')}")
        print(f"   Timestamp: {response.get('timestamp')}")
        return True
    else:
        print("❌ API health check failed")
        print(f"   Error: {response.get('error')}")
        return False

def test_message_to_summary(message_data: Dict) -> tuple[bool, Dict]:
    """Test message summarization"""
    print_step(2, "Message → Summary")
    
    print(f"📨 Input Message:")
    print(f"   User: {message_data['user_id']}")
    print(f"   Platform: {message_data['platform']}")
    print(f"   Text: {message_data['message_text']}")
    
    success, response = api_request("POST", "/api/summarize", message_data)
    
    if success:
        print("✅ Summary generated successfully")
        print(f"   Summary ID: {response['summary_id']}")
        print(f"   Summary: {response['summary']}")
        print(f"   Type: {response['type']}")
        print(f"   Intent: {response['intent']}")
        print(f"   Urgency: {response['urgency']}")
        return True, response
    else:
        print("❌ Summary generation failed")
        print(f"   Error: {response.get('error')}")
        return False, {}

def test_summary_to_task(summary_data: Dict) -> tuple[bool, Dict]:
    """Test task creation from summary"""
    print_step(3, "Summary → Task")
    
    print(f"📋 Input Summary:")
    print(f"   Summary ID: {summary_data['summary_id']}")
    print(f"   Summary: {summary_data['summary']}")
    
    success, response = api_request("POST", "/api/process_summary", summary_data)
    
    if success:
        print("✅ Task created successfully")
        print(f"   Task ID: {response['task_id']}")
        print(f"   Task Summary: {response['task_summary']}")
        print(f"   Task Type: {response['task_type']}")
        print(f"   Scheduled For: {response.get('scheduled_for', 'Not scheduled')}")
        print(f"   Status: {response['status']}")
        return True, response
    else:
        print("❌ Task creation failed")
        print(f"   Error: {response.get('error')}")
        return False, {}

def test_feedback_submission(summary_id: str) -> bool:
    """Test feedback submission"""
    print_step(4, "Feedback Submission")
    
    feedback_data = {
        "summary_id": summary_id,
        "rating": "up",
        "comment": "Excellent summary! Very accurate.",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    print(f"👍 Submitting Positive Feedback:")
    print(f"   Summary ID: {feedback_data['summary_id']}")
    print(f"   Rating: {feedback_data['rating']}")
    print(f"   Comment: {feedback_data['comment']}")
    
    success, response = api_request("POST", "/api/feedback", feedback_data)
    
    if success:
        print("✅ Feedback submitted successfully")
        return True
    else:
        print("❌ Feedback submission failed")
        print(f"   Error: {response.get('error')}")
        return False

def test_data_retrieval():
    """Test data retrieval endpoints"""
    print_step(5, "Data Retrieval")
    
    endpoints = [
        ("/api/messages", "Messages"),
        ("/api/summaries", "Summaries"),
        ("/api/tasks", "Tasks"),
        ("/api/feedback", "Feedback"),
        ("/api/stats", "Statistics")
    ]
    
    results = {}
    
    for endpoint, name in endpoints:
        print(f"🔍 Testing {name} endpoint...")
        success, response = api_request("GET", f"{endpoint}?limit=5")
        
        if success:
            if name == "Statistics":
                print(f"   ✅ {name}: {response.get('totals', {})}")
            else:
                item_count = len(response.get(name.lower(), []))
                total_count = response.get('total', 0)
                print(f"   ✅ {name}: {item_count} items (Total: {total_count})")
            
            results[name] = response
        else:
            print(f"   ❌ {name}: {response.get('error')}")
            results[name] = None
    
    return results

def test_task_status_update(task_id: str) -> bool:
    """Test task status update"""
    print_step(6, "Task Status Update")
    
    update_data = {"status": "completed"}
    
    print(f"🔄 Updating task status:")
    print(f"   Task ID: {task_id}")
    print(f"   New Status: {update_data['status']}")
    
    success, response = api_request("PUT", f"/api/tasks/{task_id}/status", update_data)
    
    if success:
        print("✅ Task status updated successfully")
        print(f"   Updated At: {response.get('updated_at')}")
        return True
    else:
        print("❌ Task status update failed")
        print(f"   Error: {response.get('error')}")
        return False

def run_complete_flow():
    """Run the complete end-to-end flow"""
    print_section("Assistant Live Demo - End-to-End Flow Test")
    print("Testing complete message processing pipeline:")
    print("Message → Summary → Task → Feedback + Data Retrieval")
    
    # Test data - various scenarios
    test_messages = [
        {
            "user_id": "demo_user",
            "platform": "email",
            "conversation_id": "e2e_test_conv",
            "message_id": f"e2e_msg_{int(time.time())}",
            "message_text": "Can we schedule a team standup for tomorrow at 10 AM?",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        },
        {
            "user_id": "test_user",
            "platform": "slack",
            "conversation_id": "e2e_test_conv_2",
            "message_id": f"e2e_msg_{int(time.time())}_2",
            "message_text": "URGENT: Production server is down, need immediate assistance!",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    ]
    
    # Step 1: Check API Health
    if not test_api_health():
        print("\\n❌ Cannot proceed - API is not healthy")
        return False
    
    success_count = 0
    total_flows = len(test_messages)
    
    for i, message in enumerate(test_messages, 1):
        print_section(f"Flow Test {i}/{total_flows}")
        
        # Step 2: Message → Summary
        summary_success, summary = test_message_to_summary(message)
        if not summary_success:
            continue
        
        # Step 3: Summary → Task
        task_success, task = test_summary_to_task(summary)
        if not task_success:
            continue
        
        # Step 4: Submit Feedback
        feedback_success = test_feedback_submission(summary['summary_id'])
        
        # Step 5: Update Task Status
        status_update_success = test_task_status_update(task['task_id'])
        
        if summary_success and task_success and feedback_success and status_update_success:
            success_count += 1
            print(f"\\n✅ Flow {i} completed successfully!")
        else:
            print(f"\\n⚠️ Flow {i} completed with some errors")
    
    # Step 6: Test Data Retrieval
    data_results = test_data_retrieval()
    
    # Final Results
    print_section("Test Results Summary")
    print(f"✅ Successful flows: {success_count}/{total_flows}")
    print(f"📊 Data endpoints tested: {len([r for r in data_results.values() if r is not None])}/{len(data_results)}")
    
    if success_count == total_flows and all(data_results.values()):
        print(f"\\n🎉 ALL TESTS PASSED! The API is ready for frontend integration.")
        print(f"\\n📋 Next Steps:")
        print(f"   1. Start frontend development using API_CONTRACT.md")
        print(f"   2. Use provided endpoints for real-time data")
        print(f"   3. Implement error handling as documented")
        print(f"   4. Test with sample data using seed_data.py")
        return True
    else:
        print(f"\\n⚠️ Some tests failed. Please check the API implementation.")
        return False

def main():
    """Main execution function"""
    print("Assistant Live Demo - End-to-End Flow Test")
    print("=" * 60)
    
    try:
        success = run_complete_flow()
        exit_code = 0 if success else 1
        
        print(f"\\n{'='*60}")
        print(f"Test execution {'COMPLETED SUCCESSFULLY' if success else 'COMPLETED WITH ERRORS'}")
        print(f"Exit code: {exit_code}")
        
        return exit_code
        
    except KeyboardInterrupt:
        print(f"\\n\\nTest interrupted by user")
        return 1
    except Exception as e:
        print(f"\\n\\nUnexpected error during testing: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)