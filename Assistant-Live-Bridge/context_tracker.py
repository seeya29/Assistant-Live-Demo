import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict, Counter
import pytz

class ContextTracker:
    """Track user context across platforms and interactions"""
    
    def __init__(self, context_dir: str = "user_contexts"):
        # Use absolute path to avoid CWD-related issues
        self.context_dir = os.path.abspath(context_dir)
        self.ensure_context_dir()
        
        # In-memory cache for active contexts
        self.active_contexts = {}
        
        # Context scoring weights
        self.scoring_weights = {
            "recency": 0.3,
            "frequency": 0.25,
            "completion_rate": 0.25,
            "platform_consistency": 0.2
        }
    
    def ensure_context_dir(self):
        """Ensure context directory exists"""
        if not os.path.exists(self.context_dir):
            os.makedirs(self.context_dir)
    
    def get_context_file_path(self, user_id: str) -> str:
        """Get file path for user's context"""
        return os.path.join(self.context_dir, f"{user_id}_context.json")
    
    def load_user_context(self, user_id: str) -> Dict[str, Any]:
        """Load user context from file"""
        context_file = self.get_context_file_path(user_id)
        
        default_context = {
            "user_id": user_id,
            "created_at": datetime.now(pytz.UTC).isoformat(),
            "last_updated": datetime.now(pytz.UTC).isoformat(),
            "message_history": [],
            "intent_patterns": {},
            "platform_usage": {},
            "message_type_frequency": {},
            "scheduled_tasks": [],
            "missed_tasks": [],
            "completed_tasks": [],
            "response_patterns": {},
            "peak_activity_hours": {},
            "context_score": 0.0,
            "behavioral_insights": {}
        }
        
        try:
            with open(context_file, 'r') as f:
                context = json.load(f)
                # Merge with default to ensure all fields exist
                for key, value in default_context.items():
                    if key not in context:
                        context[key] = value
                return context
        except FileNotFoundError:
            # Create a default file to avoid future FileNotFound errors
            try:
                os.makedirs(self.context_dir, exist_ok=True)
                with open(context_file, 'w') as f:
                    json.dump(default_context, f, indent=2, default=str)
            except Exception:
                pass
            return default_context
    
    def save_user_context(self, user_id: str, context: Dict[str, Any]):
        """Save user context to file"""
        context_file = self.get_context_file_path(user_id)
        context["last_updated"] = datetime.now(pytz.UTC).isoformat()
        
        os.makedirs(self.context_dir, exist_ok=True)
        with open(context_file, 'w') as f:
            json.dump(context, f, indent=2, default=str)
        
        # Update in-memory cache
        self.active_contexts[user_id] = context
    
    def update_context(self, user_id: str, interaction_data: Dict[str, Any]):
        """Update user context with new interaction"""
        context = self.load_user_context(user_id)
        
        # Add to message history
        message_entry = {
            "timestamp": interaction_data["timestamp"],
            "platform": interaction_data["platform"],
            "message_type": interaction_data["message_type"],
            "summary": interaction_data["summary"]
        }
        
        context["message_history"].append(message_entry)
        
        # Keep only last 100 messages
        if len(context["message_history"]) > 100:
            context["message_history"] = context["message_history"][-100:]
        
        # Update frequency counters
        # Safe increments for plain dicts
        plat = interaction_data["platform"]
        mtype = interaction_data["message_type"]
        context["platform_usage"][plat] = context["platform_usage"].get(plat, 0) + 1
        context["message_type_frequency"][mtype] = context["message_type_frequency"].get(mtype, 0) + 1
        
        # Extract hour for peak activity tracking
        try:
            timestamp = datetime.fromisoformat(interaction_data["timestamp"].replace('Z', '+00:00'))
            hour = timestamp.hour
            hour_key = str(hour)
            context["peak_activity_hours"][hour_key] = context["peak_activity_hours"].get(hour_key, 0) + 1
        except Exception:
            pass
        
        # Update intent patterns based on message content
        self._update_intent_patterns(context, interaction_data)
        
        # Calculate updated context score
        context["context_score"] = self._calculate_context_score(context)
        
        # Generate behavioral insights
        context["behavioral_insights"] = self._generate_behavioral_insights(context)
        
        self.save_user_context(user_id, context)
    
    def _update_intent_patterns(self, context: Dict[str, Any], interaction_data: Dict[str, Any]):
        """Update intent patterns based on interaction"""
        summary = interaction_data["summary"].lower()
        message_type = interaction_data["message_type"]
        
        # Intent keywords
        intent_keywords = {
            "scheduling": ["meet", "schedule", "appointment", "calendar", "time"],
            "information_seeking": ["what", "how", "when", "where", "why", "info"],
            "task_assignment": ["need", "complete", "finish", "do", "task"],
            "follow_up": ["follow", "update", "status", "progress", "check"],
            "urgent_request": ["urgent", "asap", "immediately", "emergency"],
            "social": ["hi", "hello", "thanks", "please", "lunch", "coffee"]
        }
        
        for intent, keywords in intent_keywords.items():
            if any(keyword in summary for keyword in keywords):
                context["intent_patterns"][intent] = context["intent_patterns"].get(intent, 0) + 1
        
        # Also track by message type
        type_key = f"type_{message_type}"
        context["intent_patterns"][type_key] = context["intent_patterns"].get(type_key, 0) + 1
    
    def _calculate_context_score(self, context: Dict[str, Any]) -> float:
        """Calculate overall context score for user"""
        scores = {}
        
        # Recency score (based on recent activity)
        recent_messages = [msg for msg in context["message_history"] 
                          if self._is_recent(msg["timestamp"], days=7)]
        scores["recency"] = min(len(recent_messages) / 10.0, 1.0)  # Normalize to 0-1
        
        # Frequency score (based on total interactions)
        total_interactions = len(context["message_history"])
        scores["frequency"] = min(total_interactions / 50.0, 1.0)  # Normalize to 0-1
        
        # Completion rate score
        total_tasks = len(context["scheduled_tasks"]) + len(context["completed_tasks"]) + len(context["missed_tasks"])
        if total_tasks > 0:
            completion_rate = len(context["completed_tasks"]) / total_tasks
            scores["completion_rate"] = completion_rate
        else:
            scores["completion_rate"] = 0.5  # Neutral score for new users
        
        # Platform consistency score
        platform_counts = list(context["platform_usage"].values())
        if platform_counts:
            # Higher score for consistent platform usage
            max_platform_usage = max(platform_counts)
            total_usage = sum(platform_counts)
            scores["platform_consistency"] = max_platform_usage / total_usage
        else:
            scores["platform_consistency"] = 0.5
        
        # Calculate weighted score
        weighted_score = sum(scores[key] * self.scoring_weights[key] for key in scores)
        return round(weighted_score, 3)
    
    def _is_recent(self, timestamp_str: str, days: int = 7) -> bool:
        """Check if timestamp is within recent days"""
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            cutoff = datetime.now(pytz.UTC) - timedelta(days=days)
            return timestamp > cutoff
        except Exception:
            return False
    
    def _generate_behavioral_insights(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate behavioral insights from context data"""
        insights = {}
        
        # Most active platform
        if context["platform_usage"]:
            most_active_platform = max(context["platform_usage"], key=context["platform_usage"].get)
            insights["preferred_platform"] = most_active_platform
        
        # Most common message type
        if context["message_type_frequency"]:
            common_type = max(context["message_type_frequency"], key=context["message_type_frequency"].get)
            insights["common_message_type"] = common_type
        
        # Peak activity hour
        if context["peak_activity_hours"]:
            peak_hour = max(context["peak_activity_hours"], key=context["peak_activity_hours"].get)
            insights["peak_activity_hour"] = int(peak_hour)
        
        # Dominant intent
        if context["intent_patterns"]:
            dominant_intent = max(context["intent_patterns"], key=context["intent_patterns"].get)
            insights["dominant_intent"] = dominant_intent
        
        # Activity level
        recent_activity = len([msg for msg in context["message_history"] 
                              if self._is_recent(msg["timestamp"], days=7)])
        if recent_activity >= 10:
            insights["activity_level"] = "high"
        elif recent_activity >= 5:
            insights["activity_level"] = "medium"
        else:
            insights["activity_level"] = "low"
        
        # Task completion tendency
        total_tasks = len(context["scheduled_tasks"]) + len(context["completed_tasks"]) + len(context["missed_tasks"])
        if total_tasks > 0:
            completion_rate = len(context["completed_tasks"]) / total_tasks
            if completion_rate >= 0.8:
                insights["task_completion_tendency"] = "excellent"
            elif completion_rate >= 0.6:
                insights["task_completion_tendency"] = "good"
            elif completion_rate >= 0.4:
                insights["task_completion_tendency"] = "average"
            else:
                insights["task_completion_tendency"] = "needs_improvement"
        
        return insights
    
    def get_context_score(self, user_id: str, task_type: str) -> float:
        """Get context score for specific task type"""
        context = self.load_user_context(user_id)
        base_score = context["context_score"]
        
        # Adjust score based on user's history with this task type
        type_frequency = context["message_type_frequency"].get(task_type, 0)
        total_messages = len(context["message_history"])
        
        if total_messages > 0:
            type_ratio = type_frequency / total_messages
            # Boost score if user frequently deals with this task type
            adjusted_score = base_score + (type_ratio * 0.2)
            return min(adjusted_score, 1.0)
        
        return base_score
    
    def get_user_insights(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive user insights"""
        context = self.load_user_context(user_id)
        
        return {
            "context_score": context["context_score"],
            "behavioral_insights": context["behavioral_insights"],
            "platform_preferences": dict(context["platform_usage"]),
            "message_type_distribution": dict(context["message_type_frequency"]),
            "intent_patterns": dict(context["intent_patterns"]),
            "recent_activity_count": len([msg for msg in context["message_history"] 
                                         if self._is_recent(msg["timestamp"], days=7)]),
            "total_interactions": len(context["message_history"]),
            "task_summary": {
                "scheduled": len(context["scheduled_tasks"]),
                "completed": len(context["completed_tasks"]),
                "missed": len(context["missed_tasks"])
            }
        }
    
    def add_task_to_context(self, user_id: str, task_data: Dict[str, Any], task_status: str = "scheduled"):
        """Add task to user context"""
        context = self.load_user_context(user_id)
        
        task_entry = {
            "task_id": task_data["task_id"],
            "task_type": task_data["task_type"],
            "scheduled_for": task_data.get("scheduled_for"),
            "created_at": task_data["created_at"],
            "platform": task_data["platform"]
        }
        
        if task_status == "scheduled":
            context["scheduled_tasks"].append(task_entry)
        elif task_status == "completed":
            context["completed_tasks"].append(task_entry)
        elif task_status == "missed":
            context["missed_tasks"].append(task_entry)
        
        self.save_user_context(user_id, context)
    
    def update_task_status_in_context(self, user_id: str, task_id: str, new_status: str):
        """Update task status in user context"""
        context = self.load_user_context(user_id)
        
        # Find and move task between status lists
        task_to_move = None
        source_list = None
        
        for task_list_name in ["scheduled_tasks", "completed_tasks", "missed_tasks"]:
            task_list = context[task_list_name]
            for i, task in enumerate(task_list):
                if task["task_id"] == task_id:
                    task_to_move = task_list.pop(i)
                    source_list = task_list_name
                    break
            if task_to_move:
                break
        
        if task_to_move:
            # Add to new status list
            if new_status == "completed":
                task_to_move["completed_at"] = datetime.now(pytz.UTC).isoformat()
                context["completed_tasks"].append(task_to_move)
            elif new_status == "missed":
                task_to_move["missed_at"] = datetime.now(pytz.UTC).isoformat()
                context["missed_tasks"].append(task_to_move)
            elif new_status == "scheduled":
                context["scheduled_tasks"].append(task_to_move)
            
            # Recalculate context score
            context["context_score"] = self._calculate_context_score(context)
            context["behavioral_insights"] = self._generate_behavioral_insights(context)
            
            self.save_user_context(user_id, context)
            return True
        
        return False
    
    def get_all_user_contexts(self) -> List[str]:
        """Get list of all user IDs with contexts"""
        user_ids = []
        for filename in os.listdir(self.context_dir):
            if filename.endswith('_context.json'):
                user_id = filename.replace('_context.json', '')
                user_ids.append(user_id)
        return user_ids
    
    def get_platform_trends(self) -> Dict[str, Any]:
        """Get trends across all users and platforms"""
        all_users = self.get_all_user_contexts()
        trends = {
            "platform_popularity": defaultdict(int),
            "message_type_trends": defaultdict(int),
            "intent_trends": defaultdict(int),
            "peak_hours": defaultdict(int),
            "average_context_score": 0.0,
            "total_users": len(all_users)
        }
        
        total_score = 0
        for user_id in all_users:
            context = self.load_user_context(user_id)
            
            # Aggregate platform usage
            for platform, count in context["platform_usage"].items():
                trends["platform_popularity"][platform] += count
            
            # Aggregate message types
            for msg_type, count in context["message_type_frequency"].items():
                trends["message_type_trends"][msg_type] += count
            
            # Aggregate intents
            for intent, count in context["intent_patterns"].items():
                trends["intent_trends"][intent] += count
            
            # Aggregate peak hours
            for hour, count in context["peak_activity_hours"].items():
                trends["peak_hours"][hour] += count
            
            total_score += context["context_score"]
        
        if len(all_users) > 0:
            trends["average_context_score"] = round(total_score / len(all_users), 3)
        
        return dict(trends)