import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pytz
from dateutil import parser
import dateparser
import re
from cognitive_agent import CognitiveAgent
from context_tracker import ContextTracker
import os

class ContextFlowIntegrator:
    """Main flow handler for processing platform summaries into actionable tasks"""
    
    def __init__(self):
        self.cognitive_agent = CognitiveAgent()
        # Use absolute path for user_contexts to avoid CWD issues
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.context_tracker = ContextTracker(context_dir=os.path.join(base_dir, "user_contexts"))
        self.task_queue_file = "task_queue.json"
        self.supported_platforms = ["email", "whatsapp", "instagram", "telegram", "slack"]
        self.task_types = ["meeting", "reminder", "follow-up", "urgent", "info", "action_required"]
        
        # Load existing task queue
        self.task_queue = self._load_task_queue()
        
    def process_platform_input(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input from Seeya's SmartBrief v2 module"""
        try:
            # Validate input structure
            if not self._validate_input(input_data):
                raise ValueError("Invalid input structure")
            
            user_id = input_data["user_id"]
            platform = input_data["platform"]
            message_text = input_data["message_text"]
            timestamp = input_data["timestamp"]
            summary = input_data["summary"]
            message_type = input_data["type"]
            
            # Update context tracking
            self.context_tracker.update_context(user_id, {
                "platform": platform,
                "message_type": message_type,
                "timestamp": timestamp,
                "summary": summary
            })
            
            # Generate task ID
            task_id = f"task_{uuid.uuid4().hex[:8]}"
            
            # Extract and parse scheduling information
            scheduled_time = self._extract_schedule_info(message_text, timestamp)
            
            # Classify task type using enhanced classification
            classified_type = self._classify_task_type(message_text, summary, message_type)
            
            # Extract task summary
            task_summary = self._extract_task_summary(summary, message_text)
            
            # Create task entry
            task_entry = {
                "user_id": user_id,
                "task_id": task_id,
                "platform": platform,
                "task_summary": task_summary,
                "task_type": classified_type,
                "scheduled_for": scheduled_time,
                "status": "pending",
                "created_at": datetime.now(pytz.UTC).isoformat(),
                "original_message": message_text,
                "summary": summary,
                "priority": self._calculate_priority(message_text, classified_type),
                "context_score": self.context_tracker.get_context_score(user_id, classified_type)
            }
            
            # Add to task queue
            self._add_to_task_queue(user_id, task_entry)
            
            # Generate action recommendations
            recommendations = self._generate_recommendations(task_entry)
            
            # Log for Shantanu's dashboard
            self._log_for_dashboard(task_entry, recommendations)
            
            return {
                "success": True,
                "task_entry": task_entry,
                "recommendations": recommendations,
                "context_insights": self.context_tracker.get_user_insights(user_id)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(pytz.UTC).isoformat()
            }
    
    def _validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input structure from Seeya's agent"""
        required_fields = ["user_id", "platform", "message_text", "timestamp", "summary", "type"]
        return all(field in input_data for field in required_fields)
    
    def _extract_schedule_info(self, message_text: str, timestamp: str) -> Optional[str]:
        """Extract scheduling information from message text using robust NLP parsing with fallback."""
        try:
            base_time = parser.parse(timestamp)

            # 1) Prefer robust natural language parsing
            try:
                settings = {
                    'RELATIVE_BASE': base_time,
                    'PREFER_DATES_FROM': 'future',
                    'TIMEZONE': 'UTC',
                    'RETURN_AS_TIMEZONE_AWARE': True
                }
                parsed_dt = dateparser.parse(message_text, settings=settings)
                if parsed_dt:
                    # Normalize to UTC ISO8601
                    return parsed_dt.astimezone(pytz.UTC).isoformat()
            except Exception:
                pass

            # 2) Fallback: regex-based time/date extraction
            # Time patterns
            time_patterns = [
                r'(\d{1,2})\s*(?::|\.)\s*(\d{2})\s*(?:am|pm|AM|PM)',
                r'(\d{1,2})\s*(?:am|pm|AM|PM)',
                r'at\s+(\d{1,2})\s*(?::|\.)\s*(\d{2})',
                r'at\s+(\d{1,2})\s*(?:am|pm|AM|PM)'
            ]

            # Date patterns
            date_patterns = [
                r'tomorrow',
                r'today',
                r'next\s+week',
                r'next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
                r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
                r'(\d{1,2})/(\d{1,2})/(\d{4})',
                r'(\d{1,2})-(\d{1,2})-(\d{4})'
            ]

            extracted_time = None
            for pattern in time_patterns:
                match = re.search(pattern, message_text, re.IGNORECASE)
                if match:
                    if len(match.groups()) == 2:
                        hour, minute = match.groups()
                        extracted_time = f"{hour}:{minute}"
                    else:
                        extracted_time = match.group(1)
                    break

            scheduled_date = base_time.date()
            for pattern in date_patterns:
                match = re.search(pattern, message_text, re.IGNORECASE)
                if match:
                    if 'tomorrow' in match.group(0).lower():
                        scheduled_date = base_time.date() + timedelta(days=1)
                    elif 'next week' in match.group(0).lower():
                        scheduled_date = base_time.date() + timedelta(days=7)
                    break

            if extracted_time:
                if ':' in extracted_time:
                    hour, minute = map(int, extracted_time.split(':'))
                else:
                    hour = int(extracted_time)
                    minute = 0

                # Handle AM/PM
                if 'pm' in message_text.lower() and hour < 12:
                    hour += 12
                elif 'am' in message_text.lower() and hour == 12:
                    hour = 0

                scheduled_datetime = datetime.combine(scheduled_date, datetime.min.time().replace(hour=hour, minute=minute))
                return pytz.UTC.localize(scheduled_datetime).isoformat()

            return None

        except Exception:
            return None
    
    def _classify_task_type(self, message_text: str, summary: str, suggested_type: str) -> str:
        """Enhanced task type classification"""
        text_to_analyze = f"{message_text} {summary}".lower()
        
        # Keywords for each task type
        type_keywords = {
            "meeting": ["meet", "meeting", "call", "conference", "discuss", "presentation", "demo"],
            "reminder": ["remind", "remember", "don't forget", "deadline", "due", "schedule"],
            "follow-up": ["follow up", "check", "update", "status", "progress", "follow-up"],
            "urgent": ["urgent", "asap", "immediately", "emergency", "critical", "important"],
            "action_required": ["need", "required", "must", "should", "action", "complete", "finish"],
            "info": ["info", "information", "fyi", "notice", "announcement", "update"]
        }
        
        # Score each type
        type_scores = {}
        for task_type, keywords in type_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_to_analyze)
            type_scores[task_type] = score
        
        # Use suggested type if it has keywords, otherwise use highest scoring
        if suggested_type in type_scores and type_scores[suggested_type] > 0:
            return suggested_type
        
        return max(type_scores, key=type_scores.get) if max(type_scores.values()) > 0 else suggested_type
    
    def _extract_task_summary(self, summary: str, message_text: str) -> str:
        """Extract concise task summary"""
        # Use provided summary, but clean it up
        if summary and len(summary.strip()) > 0:
            # Remove common prefixes
            cleaned = re.sub(r'^(request for|need to|should|must|please)\s+', '', summary.lower())
            return cleaned.capitalize()
        
        # Fallback to extracting from message text
        sentences = message_text.split('.')
        if sentences:
            return sentences[0][:100] + "..." if len(sentences[0]) > 100 else sentences[0]
        
        return "Task from " + message_text[:50] + "..."
    
    def _calculate_priority(self, message_text: str, task_type: str) -> str:
        """Calculate task priority"""
        text_lower = message_text.lower()
        
        # High priority indicators
        high_priority_words = ["urgent", "asap", "immediately", "critical", "emergency"]
        if any(word in text_lower for word in high_priority_words) or task_type == "urgent":
            return "high"
        
        # Medium priority indicators
        medium_priority_words = ["important", "soon", "deadline", "meeting"]
        if any(word in text_lower for word in medium_priority_words) or task_type == "meeting":
            return "medium"
        
        return "low"
    
    def _generate_recommendations(self, task_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate action recommendations based on task (robust defaults + type-specific)."""
        recommendations: List[Dict[str, Any]] = []
        
        task_type = task_entry.get("task_type", "info")
        priority = task_entry.get("priority", "medium")
        scheduled_for = task_entry.get("scheduled_for")
        summary_lower = (task_entry.get("task_summary") or "").lower()
        
        # Type-specific recommendations
        if task_type == "meeting":
            recommendations.extend([
                {"action": "calendar_block", "description": "Block time in calendar", "priority": "high"},
                {"action": "prepare_agenda", "description": "Prepare meeting agenda", "priority": "medium"},
                {"action": "send_confirmation", "description": "Send meeting confirmation", "priority": "medium"}
            ])
        elif task_type == "reminder":
            recommendations.extend([
                {"action": "set_reminder", "description": "Set reminder notification", "priority": "high"},
                {"action": "add_to_todo", "description": "Add to todo list", "priority": "medium"}
            ])
        elif task_type == "follow-up":
            recommendations.extend([
                {"action": "schedule_followup", "description": "Schedule follow-up time", "priority": "medium"},
                {"action": "gather_info", "description": "Gather required information", "priority": "high"}
            ])
        elif task_type == "action_required":
            recommendations.extend([
                {"action": "create_subtasks", "description": "Break down into actionable subtasks", "priority": "high"},
                {"action": "assign_owner", "description": "Assign responsible owner", "priority": "high"}
            ])
        elif task_type == "complaint":
            recommendations.extend([
                {"action": "acknowledge_issue", "description": "Acknowledge and gather details", "priority": "high"},
                {"action": "create_bug_ticket", "description": "Open bug/ticket with reproduction steps", "priority": "high"}
            ])
        elif task_type == "sales":
            recommendations.extend([
                {"action": "prepare_quote", "description": "Prepare quote/pricing details", "priority": "medium"},
                {"action": "followup_customer", "description": "Follow up with customer", "priority": "medium"}
            ])
        elif task_type == "delivery":
            recommendations.extend([
                {"action": "check_tracking", "description": "Check shipment tracking and ETA", "priority": "medium"},
                {"action": "notify_recipient", "description": "Notify recipient of delivery status", "priority": "low"}
            ])
        elif task_type == "cancellation":
            recommendations.extend([
                {"action": "confirm_cancellation", "description": "Confirm cancellation with stakeholder", "priority": "high"},
                {"action": "process_refund", "description": "Process refund/return if applicable", "priority": "medium"}
            ])
        elif task_type == "info":
            recommendations.extend([
                {"action": "document_info", "description": "Record key details in knowledge base", "priority": "low"}
            ])
        
        # Priority-based recommendations
        if priority == "high":
            recommendations.insert(0, {
                "action": "immediate_attention",
                "description": "Requires immediate attention",
                "priority": "critical"
            })
        
        # Scheduling recommendations
        if scheduled_for:
            recommendations.append({
                "action": "calendar_reminder",
                "description": f"Set calendar reminder for {scheduled_for}",
                "priority": "high"
            })
        else:
            # If time not parsed but text suggests scheduling, propose scheduling step
            if any(k in summary_lower for k in ["schedule", "meeting", "call", "tomorrow", "next", "am", "pm"]):
                recommendations.append({
                    "action": "suggest_schedule_parse",
                    "description": "Extract/confirm time and add to calendar",
                    "priority": "medium"
                })
        
        # Always provide a minimal default set if empty
        if not recommendations:
            recommendations.extend([
                {"action": "add_to_todo", "description": "Add to general todo list", "priority": "low"},
                {"action": "clarify_requirements", "description": "Clarify scope and next steps", "priority": "medium"}
            ])
        
        return recommendations
    
    def _add_to_task_queue(self, user_id: str, task_entry: Dict[str, Any]):
        """Add task to user's task queue"""
        if user_id not in self.task_queue:
            self.task_queue[user_id] = []
        
        self.task_queue[user_id].append(task_entry)
        self._save_task_queue()
    
    def _load_task_queue(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load task queue from file"""
        try:
            with open(self.task_queue_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def _save_task_queue(self):
        """Save task queue to file"""
        with open(self.task_queue_file, 'w') as f:
            json.dump(self.task_queue, f, indent=2, default=str)
    
    def _log_for_dashboard(self, task_entry: Dict[str, Any], recommendations: List[Dict[str, Any]]):
        """Generate logs for Shantanu's dashboard"""
        log_entry = {
            "timestamp": datetime.now(pytz.UTC).isoformat(),
            "user_id": task_entry["user_id"],
            "task_id": task_entry["task_id"],
            "platform": task_entry["platform"],
            "task_type": task_entry["task_type"],
            "priority": task_entry["priority"],
            "status": "processed",
            "recommendations_count": len(recommendations),
            "context_score": task_entry.get("context_score", 0)
        }
        
        # Append to dashboard log file
        try:
            with open("dashboard_logs.json", "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception:
            pass
    
    def get_user_tasks(self, user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get tasks for a specific user"""
        user_tasks = self.task_queue.get(user_id, [])
        if status:
            return [task for task in user_tasks if task["status"] == status]
        return user_tasks
    
    def update_task_status(self, user_id: str, task_id: str, new_status: str) -> bool:
        """Update task status"""
        user_tasks = self.task_queue.get(user_id, [])
        for task in user_tasks:
            if task["task_id"] == task_id:
                task["status"] = new_status
                task["updated_at"] = datetime.now(pytz.UTC).isoformat()
                self._save_task_queue()
                return True
        return False
    
    def get_platform_stats(self) -> Dict[str, Any]:
        """Get statistics across all platforms and users"""
        stats = {
            "total_tasks": 0,
            "platform_distribution": {},
            "type_distribution": {},
            "priority_distribution": {},
            "status_distribution": {}
        }
        
        for user_tasks in self.task_queue.values():
            for task in user_tasks:
                stats["total_tasks"] += 1
                
                # Platform distribution
                platform = task["platform"]
                stats["platform_distribution"][platform] = stats["platform_distribution"].get(platform, 0) + 1
                
                # Type distribution
                task_type = task["task_type"]
                stats["type_distribution"][task_type] = stats["type_distribution"].get(task_type, 0) + 1
                
                # Priority distribution
                priority = task["priority"]
                stats["priority_distribution"][priority] = stats["priority_distribution"].get(priority, 0) + 1
                
                # Status distribution
                status = task["status"]
                stats["status_distribution"][status] = stats["status_distribution"].get(status, 0) + 1
        
        return stats