"""
ContextLoader - Handles conversation history and context management for SmartSummarizerV3.
Provides context-aware capabilities by maintaining user conversation history.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
import os

class ContextLoader:
    """
    Manages conversation context and history for enhanced summarization.
    """
    
    def __init__(self, context_dir: str = "user_contexts", max_history: int = 50):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # Resolve to absolute path relative to this file if a relative path is provided
        if not os.path.isabs(context_dir):
            self.context_dir = os.path.join(base_dir, context_dir)
        else:
            self.context_dir = context_dir
        self.max_history = max_history
        self.memory_cache = {}
        
        # Ensure context directory exists
        os.makedirs(self.context_dir, exist_ok=True)
        
        # Context analysis patterns
        self.context_patterns = {
            'follow_up': ['following up', 'any update', 'heard back', 'progress'],
            'continuation': ['also', 'additionally', 'furthermore', 'moreover'],
            'reference': ['as discussed', 'mentioned earlier', 'previous', 'last time'],
            'urgent_escalation': ['still waiting', 'urgent', 'asap', 'deadline approaching']
        }
        
        # User behavior tracking
        self.user_patterns = defaultdict(lambda: {
            'platforms': defaultdict(int),
            'message_types': defaultdict(int),
            'response_times': [],
            'common_contacts': defaultdict(int),
            'activity_hours': defaultdict(int)
        })
        
        self._load_user_patterns()
    
    def get_conversation_context(
        self, 
        user_id: str, 
        platform: str, 
        limit: int = 10,
        time_window_hours: int = 72
    ) -> Dict[str, Any]:
        """
        Get conversation context for a user on a specific platform.
        Enhanced to specifically support the 'past 3 messages' requirement for SmartBrief v3.
        
        Args:
            user_id: User identifier
            platform: Platform (email, whatsapp, etc.)
            limit: Maximum number of previous messages
            time_window_hours: Time window for context relevance
            
        Returns:
            Dictionary containing conversation history and context analysis
        """
        try:
            # Get user context file
            context_file = os.path.join(self.context_dir, f"{user_id}_context.json")
            
            # Load context data
            context_data = self._load_context_file(context_file)
            
            # Filter by platform and time window
            cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
            relevant_history = []
            
            platform_history = context_data.get('platforms', {}).get(platform, [])
            
            for message in platform_history[-limit:]:
                try:
                    message_time = datetime.fromisoformat(message.get('timestamp', ''))
                    if message_time >= cutoff_time:
                        relevant_history.append(message)
                except:
                    # Include message if timestamp parsing fails
                    relevant_history.append(message)
            
            # Get specific past 3 messages for SmartBrief v3
            past_3_messages = self._get_past_3_messages(platform_history)
            
            # Analyze context patterns
            context_analysis = self._analyze_context_patterns(relevant_history)
            
            # Enhanced context analysis for past 3 messages
            past_3_analysis = self._analyze_past_3_context(past_3_messages) if past_3_messages else {}
            
            # Get user behavior insights
            behavior_insights = self._get_user_behavior_insights(user_id, platform)
            
            return {
                'history': relevant_history,
                'past_3_messages': past_3_messages,  # Specific for SmartBrief v3
                'context_analysis': context_analysis,
                'past_3_analysis': past_3_analysis,  # Enhanced analysis for past 3
                'behavior_insights': behavior_insights,
                'total_messages': len(platform_history),
                'time_window_hours': time_window_hours,
                'context_score': self._calculate_context_score(relevant_history, context_analysis),
                'conversation_flow': self._analyze_conversation_flow(past_3_messages)
            }
            
        except Exception as e:
            logging.error(f"Error loading context for {user_id}: {str(e)}")
            return {
                'history': [],
                'past_3_messages': [],
                'context_analysis': {},
                'past_3_analysis': {},
                'behavior_insights': {},
                'total_messages': 0,
                'time_window_hours': time_window_hours,
                'context_score': 0.0,
                'conversation_flow': {}
            }
    
    def update_context(
        self, 
        user_id: str, 
        platform: str, 
        message_data: Dict[str, Any],
        summary_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update conversation context with new message.
        
        Args:
            user_id: User identifier
            platform: Platform name
            message_data: Message information
            summary_data: Optional summary analysis data
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            context_file = os.path.join(self.context_dir, f"{user_id}_context.json")
            context_data = self._load_context_file(context_file)
            
            # Prepare message entry
            message_entry = {
                'timestamp': message_data.get('timestamp', datetime.now().isoformat()),
                'message_text': message_data.get('message_text', ''),
                'message_id': message_data.get('message_id', ''),
                'summary': summary_data.get('summary', '') if summary_data else '',
                'intent': summary_data.get('intent', '') if summary_data else '',
                'urgency': summary_data.get('urgency', '') if summary_data else '',
                'context_score': summary_data.get('context_score', 0.0) if summary_data else 0.0
            }
            
            # Add to platform history
            if 'platforms' not in context_data:
                context_data['platforms'] = {}
            if platform not in context_data['platforms']:
                context_data['platforms'][platform] = []
            
            context_data['platforms'][platform].append(message_entry)
            
            # Keep only recent messages (within limit)
            if len(context_data['platforms'][platform]) > self.max_history:
                context_data['platforms'][platform] = context_data['platforms'][platform][-self.max_history:]
            
            # Update user behavior patterns
            self._update_user_patterns(user_id, platform, message_data, summary_data)
            
            # Update metadata
            context_data['last_updated'] = datetime.now().isoformat()
            context_data['total_messages'] = context_data.get('total_messages', 0) + 1
            
            # Save updated context
            self._save_context_file(context_file, context_data)
            
            # Update cache
            self.memory_cache[user_id] = context_data
            
            return True
            
        except Exception as e:
            logging.error(f"Error updating context for {user_id}: {str(e)}")
            return False
    
    def _load_context_file(self, context_file: str) -> Dict[str, Any]:
        """Load context data from file or return empty structure."""
        try:
            os.makedirs(os.path.dirname(context_file), exist_ok=True)
            if os.path.exists(context_file):
                with open(context_file, 'r') as f:
                    return json.load(f)
            else:
                return {
                    'user_id': os.path.basename(context_file).replace('_context.json', ''),
                    'platforms': {},
                    'created_at': datetime.now().isoformat(),
                    'last_updated': datetime.now().isoformat(),
                    'total_messages': 0
                }
        except Exception as e:
            logging.error(f"Error loading context file {context_file}: {str(e)}")
            return {'platforms': {}, 'total_messages': 0}
    
    def _save_context_file(self, context_file: str, context_data: Dict[str, Any]) -> bool:
        """Save context data to file."""
        try:
            os.makedirs(os.path.dirname(context_file), exist_ok=True)
            with open(context_file, 'w') as f:
                json.dump(context_data, f, indent=2, default=str)
            return True
        except Exception as e:
            logging.error(f"Error saving context file {context_file}: {str(e)}")
            return False
    
    def _analyze_context_patterns(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze patterns in conversation history."""
        if not history:
            return {}
        
        analysis = {
            'conversation_length': len(history),
            'patterns_detected': [],
            'topic_continuity': 0.0,
            'urgency_trend': 'stable',
            'recent_intents': []
        }
        
        # Extract recent intents
        recent_intents = [msg.get('intent', '') for msg in history[-5:] if msg.get('intent')]
        analysis['recent_intents'] = recent_intents
        
        # Check for conversation patterns
        message_texts = [msg.get('message_text', '').lower() for msg in history]
        combined_text = ' '.join(message_texts)
        
        for pattern_name, keywords in self.context_patterns.items():
            if any(keyword in combined_text for keyword in keywords):
                analysis['patterns_detected'].append(pattern_name)
        
        # Analyze urgency trend
        urgency_scores = []
        urgency_map = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        
        for msg in history:
            urgency = msg.get('urgency', 'medium')
            urgency_scores.append(urgency_map.get(urgency, 2))
        
        if len(urgency_scores) >= 2:
            if urgency_scores[-1] > urgency_scores[0]:
                analysis['urgency_trend'] = 'increasing'
            elif urgency_scores[-1] < urgency_scores[0]:
                analysis['urgency_trend'] = 'decreasing'
        
        # Calculate topic continuity (simplified keyword overlap)
        if len(history) >= 2:
            last_words = set(history[-1].get('message_text', '').lower().split())
            prev_words = set(history[-2].get('message_text', '').lower().split())
            
            if last_words and prev_words:
                overlap = len(last_words & prev_words)
                total_unique = len(last_words | prev_words)
                analysis['topic_continuity'] = overlap / total_unique if total_unique > 0 else 0.0
        
        return analysis
    
    def _get_user_behavior_insights(self, user_id: str, platform: str) -> Dict[str, Any]:
        """Get user behavior insights."""
        if user_id not in self.user_patterns:
            return {}
        
        patterns = self.user_patterns[user_id]
        
        insights = {
            'primary_platforms': sorted(patterns['platforms'].items(), key=lambda x: x[1], reverse=True)[:3],
            'common_message_types': sorted(patterns['message_types'].items(), key=lambda x: x[1], reverse=True)[:3],
            'peak_activity_hours': self._get_peak_hours(patterns['activity_hours']),
            'avg_response_time_minutes': self._calculate_avg_response_time(patterns['response_times']),
            'platform_preference': max(patterns['platforms'], key=patterns['platforms'].get) if patterns['platforms'] else 'unknown'
        }
        
        return insights
    
    def _update_user_patterns(
        self, 
        user_id: str, 
        platform: str, 
        message_data: Dict[str, Any],
        summary_data: Optional[Dict[str, Any]] = None
    ):
        """Update user behavior patterns."""
        patterns = self.user_patterns[user_id]
        
        # Update platform usage
        patterns['platforms'][platform] += 1
        
        # Update message types
        if summary_data and 'intent' in summary_data:
            patterns['message_types'][summary_data['intent']] += 1
        
        # Update activity hours
        try:
            timestamp = datetime.fromisoformat(message_data.get('timestamp', ''))
            hour = timestamp.hour
            patterns['activity_hours'][hour] += 1
        except:
            pass
        
        # Update common contacts (if available)
        sender = message_data.get('sender', '')
        if sender:
            patterns['common_contacts'][sender] += 1
    
    def _get_peak_hours(self, activity_hours: Dict[int, int]) -> List[int]:
        """Get peak activity hours."""
        if not activity_hours:
            return []
        
        sorted_hours = sorted(activity_hours.items(), key=lambda x: x[1], reverse=True)
        return [hour for hour, count in sorted_hours[:3]]
    
    def _calculate_avg_response_time(self, response_times: List[float]) -> float:
        """Calculate average response time in minutes."""
        if not response_times:
            return 0.0
        return sum(response_times) / len(response_times)
    
    def _calculate_context_score(self, history: List[Dict[str, Any]], analysis: Dict[str, Any]) -> float:
        """Calculate context relevance score."""
        if not history:
            return 0.0
        
        score = 0.5  # Base score
        
        # More recent messages increase score
        if len(history) >= 3:
            score += 0.2
        
        # Pattern detection increases score
        patterns_detected = len(analysis.get('patterns_detected', []))
        score += min(0.3, patterns_detected * 0.1)
        
        # Topic continuity increases score
        continuity = analysis.get('topic_continuity', 0.0)
        score += continuity * 0.2
        
        return min(1.0, score)
    
    def _get_past_3_messages(self, platform_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get the past 3 messages from platform history for SmartBrief v3 context."""
        if len(platform_history) <= 3:
            return platform_history
        return platform_history[-3:]
    
    def _analyze_past_3_context(self, past_3_messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze context patterns specifically for the past 3 messages."""
        if not past_3_messages:
            return {}
        
        analysis = {
            'message_count': len(past_3_messages),
            'intent_sequence': [],
            'urgency_progression': [],
            'topic_keywords': [],
            'conversation_type': 'unknown',
            'follow_up_detected': False,
            'escalation_detected': False,
            'context_relevance': 0.0
        }
        
        # Extract intent and urgency sequence
        for msg in past_3_messages:
            intent = msg.get('intent', 'unknown')
            urgency = msg.get('urgency', 'medium')
            analysis['intent_sequence'].append(intent)
            analysis['urgency_progression'].append(urgency)
        
        # Extract key topic keywords
        all_text = ' '.join([msg.get('message_text', '') for msg in past_3_messages]).lower()
        words = [w for w in all_text.split() if len(w) > 3 and w.isalpha()]
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # Get top keywords
        top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        analysis['topic_keywords'] = [kw[0] for kw in top_keywords]
        
        # Detect conversation patterns
        analysis['conversation_type'] = self._classify_conversation_type(past_3_messages)
        
        # Detect follow-up patterns
        follow_up_indicators = ['following up', 'any update', 'heard back', 'progress', 'status']
        if any(indicator in all_text for indicator in follow_up_indicators):
            analysis['follow_up_detected'] = True
        
        # Detect escalation patterns
        urgency_map = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        urgency_scores = [urgency_map.get(u, 2) for u in analysis['urgency_progression']]
        if len(urgency_scores) >= 2 and urgency_scores[-1] > urgency_scores[0]:
            analysis['escalation_detected'] = True
        
        # Calculate context relevance
        analysis['context_relevance'] = self._calculate_past_3_relevance(past_3_messages)
        
        return analysis
    
    def _classify_conversation_type(self, messages: List[Dict[str, Any]]) -> str:
        """Classify the type of conversation based on past 3 messages."""
        if not messages:
            return 'unknown'
        
        all_text = ' '.join([msg.get('message_text', '') for msg in messages]).lower()
        
        # Check for different conversation types
        if any(word in all_text for word in ['meeting', 'call', 'schedule', 'appointment']):
            return 'meeting_coordination'
        elif any(word in all_text for word in ['project', 'task', 'deadline', 'work']):
            return 'work_discussion'
        elif any(word in all_text for word in ['urgent', 'emergency', 'critical', 'asap']):
            return 'urgent_matter'
        elif any(word in all_text for word in ['update', 'status', 'progress', 'report']):
            return 'status_inquiry'
        elif any(word in all_text for word in ['question', '?', 'how', 'what', 'when']):
            return 'information_seeking'
        elif any(word in all_text for word in ['thanks', 'thank you', 'great', 'good']):
            return 'social_interaction'
        else:
            return 'general_communication'
    
    def _calculate_past_3_relevance(self, messages: List[Dict[str, Any]]) -> float:
        """Calculate how relevant the past 3 messages are to current context."""
        if not messages:
            return 0.0
        
        relevance_score = 0.0
        
        # Time recency factor
        try:
            latest_time = datetime.fromisoformat(messages[-1].get('timestamp', ''))
            now = datetime.now()
            hours_since = (now - latest_time).total_seconds() / 3600
            
            if hours_since < 1:
                relevance_score += 0.4  # Very recent
            elif hours_since < 24:
                relevance_score += 0.3  # Within day
            elif hours_since < 72:
                relevance_score += 0.2  # Within 3 days
            else:
                relevance_score += 0.1  # Older
        except:
            relevance_score += 0.2  # Default if timestamp parsing fails
        
        # Intent continuity factor
        intents = [msg.get('intent', '') for msg in messages if msg.get('intent')]
        if len(set(intents)) == 1:  # Same intent throughout
            relevance_score += 0.2
        elif len(set(intents)) <= 2:  # Related intents
            relevance_score += 0.1
        
        # Keyword overlap factor
        all_texts = [msg.get('message_text', '') for msg in messages]
        if len(all_texts) >= 2:
            words1 = set(all_texts[0].lower().split())
            words2 = set(all_texts[-1].lower().split())
            if words1 and words2:
                overlap = len(words1 & words2) / len(words1 | words2)
                relevance_score += overlap * 0.3
        
        return min(1.0, relevance_score)
    
    def _analyze_conversation_flow(self, past_3_messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze the flow and progression of the conversation."""
        if not past_3_messages:
            return {}
        
        flow_analysis = {
            'message_count': len(past_3_messages),
            'flow_type': 'unknown',
            'progression': 'neutral',
            'next_likely_intent': 'unknown',
            'conversation_status': 'ongoing'
        }
        
        # Analyze flow patterns
        intents = [msg.get('intent', 'unknown') for msg in past_3_messages]
        
        # Common flow patterns
        if intents == ['question', 'information', 'confirmation']:
            flow_analysis['flow_type'] = 'question_answer_confirm'
            flow_analysis['next_likely_intent'] = 'social'
        elif 'request' in intents and 'follow_up' in intents:
            flow_analysis['flow_type'] = 'request_follow_up'
            flow_analysis['next_likely_intent'] = 'information'
        elif intents.count('meeting') >= 2:
            flow_analysis['flow_type'] = 'meeting_coordination'
            flow_analysis['next_likely_intent'] = 'confirmation'
        elif 'urgent' in intents:
            flow_analysis['flow_type'] = 'urgent_escalation'
            flow_analysis['next_likely_intent'] = 'task'
        
        # Analyze progression
        urgency_map = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        urgencies = [msg.get('urgency', 'medium') for msg in past_3_messages]
        urgency_scores = [urgency_map.get(u, 2) for u in urgencies]
        
        if len(urgency_scores) >= 2:
            if urgency_scores[-1] > urgency_scores[0]:
                flow_analysis['progression'] = 'escalating'
            elif urgency_scores[-1] < urgency_scores[0]:
                flow_analysis['progression'] = 'de-escalating'
        
        # Determine conversation status
        last_intent = intents[-1] if intents else 'unknown'
        if last_intent in ['confirmation', 'social']:
            flow_analysis['conversation_status'] = 'concluding'
        elif last_intent in ['question', 'request']:
            flow_analysis['conversation_status'] = 'awaiting_response'
        elif last_intent == 'urgent':
            flow_analysis['conversation_status'] = 'requires_action'
        
        return flow_analysis
    
    def _load_user_patterns(self):
        """Load user behavior patterns from file."""
        try:
            patterns_file = os.path.join(self.context_dir, 'user_patterns.json')
            if os.path.exists(patterns_file):
                with open(patterns_file, 'r') as f:
                    data = json.load(f)
                    for user_id, patterns in data.items():
                        self.user_patterns[user_id] = defaultdict(lambda: defaultdict(int), patterns)
        except Exception as e:
            logging.error(f"Error loading user patterns: {str(e)}")
    
    def save_user_patterns(self):
        """Save user behavior patterns to file."""
        try:
            patterns_file = os.path.join(self.context_dir, 'user_patterns.json')
            
            # Convert defaultdicts to regular dicts for JSON serialization
            patterns_data = {}
            for user_id, patterns in self.user_patterns.items():
                patterns_data[user_id] = {
                    'platforms': dict(patterns['platforms']),
                    'message_types': dict(patterns['message_types']),
                    'response_times': patterns['response_times'],
                    'common_contacts': dict(patterns['common_contacts']),
                    'activity_hours': dict(patterns['activity_hours'])
                }
            
            with open(patterns_file, 'w') as f:
                json.dump(patterns_data, f, indent=2)
                
        except Exception as e:
            logging.error(f"Error saving user patterns: {str(e)}")
    
    def get_user_context_summary(self, user_id: str) -> Dict[str, Any]:
        """Get summary of user's context across all platforms."""
        try:
            context_file = os.path.join(self.context_dir, f"{user_id}_context.json")
            context_data = self._load_context_file(context_file)
            
            summary = {
                'user_id': user_id,
                'total_messages': context_data.get('total_messages', 0),
                'platforms': list(context_data.get('platforms', {}).keys()),
                'last_activity': context_data.get('last_updated', ''),
                'behavior_insights': self._get_user_behavior_insights(user_id, '')
            }
            
            # Platform breakdown
            platform_stats = {}
            for platform, messages in context_data.get('platforms', {}).items():
                platform_stats[platform] = {
                    'message_count': len(messages),
                    'last_message': messages[-1].get('timestamp', '') if messages else ''
                }
            
            summary['platform_breakdown'] = platform_stats
            
            return summary
            
        except Exception as e:
            logging.error(f"Error getting context summary for {user_id}: {str(e)}")
            return {'user_id': user_id, 'error': str(e)}
    
    def cleanup_old_contexts(self, days_old: int = 30):
        """Clean up context files older than specified days."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            for filename in os.listdir(self.context_dir):
                if filename.endswith('_context.json'):
                    filepath = os.path.join(self.context_dir, filename)
                    
                    # Check file modification time
                    file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                    
                    if file_time < cutoff_date:
                        # Load and check last_updated in file
                        context_data = self._load_context_file(filepath)
                        last_updated = context_data.get('last_updated', '')
                        
                        if last_updated:
                            last_update_time = datetime.fromisoformat(last_updated)
                            if last_update_time < cutoff_date:
                                os.remove(filepath)
                                logging.info(f"Removed old context file: {filename}")
                        
        except Exception as e:
            logging.error(f"Error during context cleanup: {str(e)}")