"""
SmartBrief v3 - Context-Aware, Platform-Agnostic Message Summarizer
Enhanced version with context intelligence, improved intent/urgency heuristics, and feedback-driven learning.
"""

import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

# Optional lightweight time parsing (used for urgency proximity)
try:
    import dateparser  # already in requirements
except Exception:
    dateparser = None

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SmartSummarizerV3:
    """
    Advanced message summarizer with context awareness and platform optimization.
    
    Features:
    - Context-aware summarization using conversation history
    - Platform-specific optimization (WhatsApp, Email, Slack, etc.)
    - Improved intent detection (multi-signal heuristics)
    - Improved urgency analysis (signals: keywords, punctuation, ALL-CAPS, time proximity)
    - Feedback-driven learning trace (term weights persist in summarizer_learning.json)
    """
    
    def __init__(self, context_file: str = 'message_context.json', max_context_messages: int = 3, confidence_threshold: float = 0.6):
        self.context_file = context_file
        self.max_context_messages = max_context_messages
        self.confidence_threshold = confidence_threshold
        
        # Load existing context
        self.context_data = self._load_context()

        # Learning store (persistent across runs)
        self.learning_file = 'summarizer_learning.json'
        self.learning = self._load_learning()
        self.term_weights: Dict[str, float] = self.learning.get('term_weights', {})
        
        # Platform-specific settings
        self.platform_configs = {
            'whatsapp': {
                'max_summary_length': 50,
                'emoji_friendly': True,
                'casual_tone': True,
                'abbreviations': True
            },
            'email': {
                'max_summary_length': 100,
                'emoji_friendly': False,
                'casual_tone': False,
                'abbreviations': False
            },
            'slack': {
                'max_summary_length': 75,
                'emoji_friendly': True,
                'casual_tone': True,
                'abbreviations': True
            },
            'teams': {
                'max_summary_length': 80,
                'emoji_friendly': False,
                'casual_tone': False,
                'abbreviations': False
            },
            'instagram': {
                'max_summary_length': 40,
                'emoji_friendly': True,
                'casual_tone': True,
                'abbreviations': True
            },
            'discord': {
                'max_summary_length': 60,
                'emoji_friendly': True,
                'casual_tone': True,
                'abbreviations': True
            }
        }
        
        # Intent patterns (base signals; scoring is weighted later)
        self.intent_patterns = {
            'question': [
                r'\?', r'\bwhat\b', r'\bhow\b', r'\bwhen\b', r'\bwhere\b', 
                r'\bwhy\b', r'\bwhich\b', r'\bwho\b', r'\bcan you\b', r'\bcould you\b'
            ],
            'request': [
                r'\bplease\b', r'\bcould you\b', r'\bwould you\b', r'\bcan you\b',
                r'\bneed\b', r'\brequire\b', r'\bwant\b', r'\bsend me\b', r'\bshare\b', r'\bprovide\b'
            ],
            'follow_up': [
                r'\bfollow.?up\b', r'\bupdate\b', r'\bstatus\b', r'\bprogress\b',
                r'\bany news\b', r'\bping\b', r'\bnudge\b', r'\bcheck in\b'
            ],
            'complaint': [
                r'\bissue\b', r'\bproblem\b', r'\berror\b', r'\bbug\b', r'\bwrong\b',
                r'\bnot working\b', r'\bbroken\b', r'\bfailed\b', r'\bdisappointed\b', r'\bdelay\b'
            ],
            'appreciation': [
                r'\bthank\b', r'\bthanks\b', r'\bappreciate\b', r'\bgreat\b',
                r'\bawesome\b', r'\bexcellent\b', r'\bgood job\b', r'\bwell done\b'
            ],
            'urgent': [
                r'\burgent\b', r'\basap\b', r'\bemergency\b', r'\bcritical\b',
                r'\bimmediately\b', r'\bright now\b', r'\bdeadline today\b', r'\bblocker\b'
            ],
            'schedule': [
                r'\bmeeting\b', r'\bappointment\b', r'\bschedule\b', r'\bcalendar\b',
                r'\btime\b', r'\bdate\b', r'\btomorrow\b', r'\bnext week\b', r'\breschedule\b'
            ],
            'sales': [
                r'\binvoice\b', r'\bpayment\b', r'\bbilling\b', r'\bpricing\b', r'\bquote\b', r'\bpo\b'
            ],
            'delivery': [
                r'\bship\b', r'\bshipping\b', r'\bdeliver\b', r'\bdelivery\b', r'\btracking\b'
            ],
            'cancellation': [
                r'\bcancel\b', r'\bcancellation\b', r'\brefund\b', r'\breturn\b'
            ],
            'social': [
                r"\banyone interested\b", r"\bjoin\b", r"\bcome\b", r"\bgo to\b", r"\bhang out\b",
                r"\bparty\b", r"\bmall\b", r"\bshopping\b", r"\bmovie\b", r"\bcinema\b", r"\bwatch\b"
            ],
            'check_progress': [
                r'\bprogress\b', r'\bstatus\b', r'\bhow.?s.*going\b', r'\bupdate\b',
                r'\bdone\b', r'\bfinished\b', r'\bcomplete\b', r'\bready\b'
            ]
        }
        
        # Urgency indicators
        self.urgency_indicators = {
            'high': [
                r'\burgent\b', r'\basap\b', r'\bemergency\b', r'\bcritical\b',
                r'\bimmediately\b', r'\bright now\b', r'\bdeadline today\b', r'\bblocker\b'
            ],
            'medium': [
                r'\bsoon\b', r'\bquickly\b', r'\bpriority\b', r'\bimportant\b',
                r'\bdeadline\b', r'\bby tomorrow\b', r'\bthis week\b'
            ],
            'low': [
                r'\bwhen you can\b', r'\bno rush\b', r'\bwhenever\b',
                r'\bno hurry\b', r'\btake your time\b'
            ]
        }
        
        # Statistics tracking
        self.stats = {
            'processed': 0,
            'context_used': 0,
            'platforms': {},
            'intents': {},
            'urgency_levels': {},
            'unique_users': set()
        }
    
    def _load_context(self) -> Dict:
        """Load conversation context from file."""
        if os.path.exists(self.context_file):
            try:
                with open(self.context_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Clean old messages (older than 30 days)
                    self._cleanup_old_context(data)
                    return data
            except Exception as e:
                logger.error(f"Error loading context: {e}")
        
        return {'conversations': {}, 'user_profiles': {}}

    def _save_context(self):
        """Save conversation context to file."""
        try:
            with open(self.context_file, 'w', encoding='utf-8') as f:
                json.dump(self.context_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving context: {e}")

    def _load_learning(self) -> Dict:
        """Load learning store (feedback history and term weights)."""
        try:
            if os.path.exists(self.learning_file):
                with open(self.learning_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if 'term_weights' not in data:
                    data['term_weights'] = {}
                return data
        except Exception as e:
            logger.warning(f"Failed to load learning file: {e}")
        return {'feedback_history': [], 'performance_metrics': {}, 'term_weights': {}, 'last_updated': datetime.now().isoformat()}
    
    def _save_learning(self):
        """Persist learning store."""
        try:
            self.learning['term_weights'] = self.term_weights
            self.learning['last_updated'] = datetime.now().isoformat()
            with open(self.learning_file, 'w', encoding='utf-8') as f:
                json.dump(self.learning, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save learning file: {e}")
    
    def _cleanup_old_context(self, data: Dict):
        """Remove messages older than 30 days."""
        cutoff_date = datetime.now() - timedelta(days=30)
        cutoff_timestamp = cutoff_date.timestamp()
        
        conversations = data.get('conversations', {})
        for user_platform, messages in conversations.items():
            # Filter out old messages
            data['conversations'][user_platform] = [
                msg for msg in messages
                if datetime.fromisoformat(msg.get('timestamp', '1970-01-01T00:00:00')).timestamp() > cutoff_timestamp
            ]
    
    def _get_context_key(self, user_id: str, platform: str) -> str:
        """Generate context key for user-platform combination."""
        return f"{user_id}_{platform}"
    
    def _extract_context(self, user_id: str, platform: str) -> List[Dict]:
        """Extract relevant context messages for a user-platform combination."""
        context_key = self._get_context_key(user_id, platform)
        conversations = self.context_data.get('conversations', {})
        
        if context_key in conversations:
            # Return last N messages
            messages = conversations[context_key]
            return messages[-self.max_context_messages:] if messages else []
        
        return []
    
    def _store_message_context(self, message_data: Dict):
        """Store message in context for future reference."""
        user_id = message_data.get('user_id', 'unknown')
        platform = message_data.get('platform', 'unknown')
        context_key = self._get_context_key(user_id, platform)
        
        # Initialize if not exists
        if 'conversations' not in self.context_data:
            self.context_data['conversations'] = {}
        
        if context_key not in self.context_data['conversations']:
            self.context_data['conversations'][context_key] = []
        
        # Add message to context
        context_message = {
            'message_text': message_data.get('message_text', ''),
            'timestamp': message_data.get('timestamp', datetime.now().isoformat()),
            'message_id': message_data.get('message_id', f"msg_{datetime.now().timestamp()}")
        }
        
        self.context_data['conversations'][context_key].append(context_message)
        
        # Keep only recent messages
        if len(self.context_data['conversations'][context_key]) > self.max_context_messages * 2:
            self.context_data['conversations'][context_key] = \
                self.context_data['conversations'][context_key][-self.max_context_messages * 2:]
        
        self._save_context()
    
    def _classify_intent(self, text: str, context_messages: List[Dict] = None) -> tuple:
        """Classify the intent of the message with multi-signal heuristics."""
        text_lower = text.lower()
        intent_scores: Dict[str, float] = {}

        # Base pattern scoring
        for intent, patterns in self.intent_patterns.items():
            score = 0.0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower))
                score += matches
            intent_scores[intent] = score

        # Direct question mark gets strong boost
        if text_lower.strip().endswith('?'):
            intent_scores['question'] = intent_scores.get('question', 0) + 2.0
            # If it's a social invite phrased as a question, favor 'social'
            if intent_scores.get('social', 0) >= 2:
                intent_scores['social'] = intent_scores.get('social', 0) + 2.0

        # Verb/action cues
        action_cues = {
            'request': ['need', 'require', 'please', 'share', 'send', 'provide', 'approve', 'fix', 'resolve'],
            'schedule': ['schedule', 'meeting', 'call', 'book', 'reschedule'],
            'follow_up': ['follow up', 'check', 'update', 'status', 'progress']
        }
        for intent, cues in action_cues.items():
            if any(cue in text_lower for cue in cues):
                intent_scores[intent] = intent_scores.get(intent, 0) + 1.0

        # Context-aware adjustment: continuity boosts follow-up
        if context_messages:
            last_msgs = ' '.join(m.get('message_text', '').lower() for m in context_messages[-3:])
            overlap = len(set(re.findall(r"\b\w+\b", text_lower)).intersection(set(re.findall(r"\b\w+\b", last_msgs))))
            if overlap > 3:
                intent_scores['follow_up'] = intent_scores.get('follow_up', 0) + 1.5

        # Choose best
        best_intent = max(intent_scores.keys(), key=lambda k: intent_scores[k]) if intent_scores else 'informational'
        max_score = intent_scores.get(best_intent, 0.0)
        # Normalize confidence to 0..1 range with a soft cap
        confidence = min(1.0, 0.2 + (max_score / 5.0))
        return best_intent, confidence
    
    def _analyze_urgency(self, text: str, context_messages: List[Dict] = None) -> tuple:
        """Analyze the urgency level using keywords, punctuation, ALL-CAPS, and time proximity."""
        text_lower = text.lower()
        urgency_score = 0.0

        # Keyword-based
        for level, patterns in self.urgency_indicators.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower))
                if level == 'high':
                    urgency_score += 2.0 * matches
                elif level == 'medium':
                    urgency_score += 1.0 * matches
                else:
                    urgency_score += 0.5 * matches

        # Punctuation and ALL-CAPS cues
        exclamations = text.count('!')
        if exclamations >= 1:
            urgency_score += min(3.0, 0.5 * exclamations)
        all_caps_tokens = sum(1 for w in re.findall(r"\b[A-Z]{3,}\b", text) if w not in ('LOL', 'FYI'))
        urgency_score += min(2.0, 0.3 * all_caps_tokens)

        # Time proximity (if parseable and near-term)
        try:
            if dateparser is not None:
                parsed = dateparser.parse(text, settings={'PREFER_DATES_FROM': 'future'})
                if parsed:
                    delta = parsed - datetime.now(parsed.tzinfo) if parsed.tzinfo else parsed - datetime.now()
                    if delta.total_seconds() < 0:
                        pass
                    elif delta.total_seconds() <= 24 * 3600:
                        urgency_score += 2.0  # within 24h
                    elif delta.total_seconds() <= 72 * 3600:
                        urgency_score += 1.0  # within 72h
        except Exception:
            pass

        # Context-aware escalation
        if context_messages:
            prev_text = ' '.join(m.get('message_text', '').lower() for m in context_messages[-3:])
            prev_high = sum(1 for w in ['urgent', 'asap', 'immediately', 'critical'] if w in prev_text)
            cur_high = sum(1 for w in ['urgent', 'asap', 'immediately', 'critical'] if w in text_lower)
            if cur_high > prev_high:
                urgency_score += 1.0

        # Map numeric score to label
        if urgency_score >= 3.5:
            return 'critical', min(1.0, 0.6 + urgency_score / 10.0)
        elif urgency_score >= 2.0:
            return 'high', min(1.0, 0.5 + urgency_score / 10.0)
        elif urgency_score >= 1.0:
            return 'medium', min(1.0, 0.4 + urgency_score / 10.0)
        else:
            return 'low', 0.3 + min(0.2, urgency_score / 10.0)
    
    def _analyze_context(self, current_message: Dict, context_messages: List[Dict]) -> List[str]:
        """Analyze conversation context for insights."""
        insights = []
        
        if not context_messages:
            return insights
        
        current_text = current_message.get('message_text', '').lower()
        
        # Look for conversation patterns
        recent_messages = context_messages[-3:] if len(context_messages) >= 3 else context_messages
        
        # Check for follow-up patterns
        follow_up_keywords = ['update', 'status', 'any news', 'heard back', 'follow up', 'did.*get done']
        if any(re.search(keyword, current_text) for keyword in follow_up_keywords):
            insights.append("This appears to be a follow-up to previous conversation")
        
        # Check for escalating urgency
        previous_texts = [msg.get('message_text', '').lower() for msg in recent_messages]
        urgency_words = ['urgent', 'asap', 'immediately', 'critical', 'deadline']
        
        current_urgency = sum(1 for word in urgency_words if word in current_text)
        previous_urgency = sum(sum(1 for word in urgency_words if word in text) for text in previous_texts)
        
        if current_urgency > previous_urgency:
            insights.append("Urgency level has increased compared to previous messages")
        
        # Check for topic continuity
        if recent_messages:
            last_message_text = recent_messages[-1].get('message_text', '').lower()
            
            # Simple keyword overlap check
            current_words = set(re.findall(r'\b\w+\b', current_text))
            last_words = set(re.findall(r'\b\w+\b', last_message_text))
            
            overlap = len(current_words.intersection(last_words))
            if overlap > 2:
                insights.append("Continues previous conversation topic")
        
        # Check for sentiment shift
        positive_words = ['thanks', 'great', 'good', 'excellent', 'appreciate']
        negative_words = ['problem', 'issue', 'wrong', 'error', 'disappointed']
        
        current_positive = sum(1 for word in positive_words if word in current_text)
        current_negative = sum(1 for word in negative_words if word in current_text)
        
        if current_positive > 0 and len(recent_messages) > 0:
            insights.append("Positive sentiment detected - possibly expressing gratitude")
        elif current_negative > 0:
            insights.append("Negative sentiment detected - may indicate frustration")
        
        return insights
        
    def _generate_summary(self, text: str, platform: str, intent: str, urgency: str, context_insights: List[str]) -> str:
        """Generate a concise, meaningful summary using extractive scoring and learning weights."""
        config = self.platform_configs.get(platform, self.platform_configs['email'])
        max_length = config['max_summary_length']

        # Internal helpers
        def _clean_message(t: str) -> str:
            t = t.strip()
            t = re.sub(r"^(hi|hello|hey|dear)\b[,\s:-]*", "", t, flags=re.IGNORECASE)
            t = re.sub(r"\b(please|kindly|could you|would you|can you|thanks|thank you)\b", "", t, flags=re.IGNORECASE)
            t = re.sub(r"\s+", " ", t)
            return t.strip()

        def _extract_time_phrase(t: str) -> str:
            patterns = [
                r"\b(today|tomorrow|tonight|this (morning|afternoon|evening))\b",
                r"\b(next (mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b",
                r"\b(next (week|month))\b",
                r"\b(\d{1,2}(:\d{2})?\s?(am|pm))\b",
                r"\b(\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?)\b",
            ]
            for p in patterns:
                m = re.search(p, t, flags=re.IGNORECASE)
                if m:
                    return m.group(0)
            return ""

        cleaned = _clean_message(text)
        sentences = re.split(r'(?<=[.!?])\s+', cleaned)
        sentences = [s.strip(" -") for s in sentences if s.strip()]
        time_phrase = _extract_time_phrase(cleaned)

        # Prebuilt summary for specific intents (e.g., social invites)
        prebuilt_summary = None
        if intent == 'social':
            activities = []
            cl = cleaned.lower()
            if ('mall' in cl) or ('shopping' in cl):
                activities.append('mall shopping')
            if any(k in cl for k in ['latest movie', 'movie', 'cinema', 'film']):
                activities.append('latest movie')
            phrase = ' + '.join(activities) if activities else 'hangout'
            base = f"Invite: {phrase}"
            if time_phrase and time_phrase.lower() not in base.lower():
                base = f"{base} {time_phrase}"
            prebuilt_summary = base

        # Frequency-based scoring plus learned term weights
        stopwords = {
            'the','a','an','and','or','but','if','on','in','at','to','for','from','of','with',
            'is','am','are','was','were','be','been','being','as','by','this','that','those','these',
            'it','its','we','you','your','our','i','me','my','they','them','their','he','she','his','her',
            'will','shall','would','could','should','can','may','might','do','does','did','have','has','had',
            'so','just','also','too','very','there','here','into','over','about','regarding','subject'
        }
        words = re.findall(r"\b[\w'-]+\b", cleaned.lower())
        freq: Dict[str, int] = {}
        for w in words:
            if len(w) < 3 or w in stopwords:
                continue
            freq[w] = freq.get(w, 0) + 1

        def _score_sentence(s: str) -> float:
            sl = s.lower()
            score = 0.0
            for w in re.findall(r"\b[\w'-]+\b", sl):
                if len(w) >= 3 and w not in stopwords:
                    score += freq.get(w, 0)
                    # learned term weight
                    if w in self.term_weights:
                        score += self.term_weights[w]
            # Boost for actionable verbs and entities
            if re.search(r"\b(schedule|meeting|call|review|deadline|submit|send|follow up|update|remind|confirm|approve|fix|resolve)\b", sl):
                score += 5
            if time_phrase and time_phrase.lower() in sl:
                score += 3
            if re.search(r"\d", sl):
                score += 1
            if intent in ('schedule','request','question','follow_up','check_progress'):
                score += 1
            return score

        best_sentence = max(sentences, key=_score_sentence) if sentences else cleaned

        # Clean and compress the chosen sentence
        best_sentence = re.sub(r"\b(please|kindly|could you|would you|can you|thanks|thank you)\b", "", best_sentence, flags=re.IGNORECASE)
        best_sentence = re.sub(r"\s+", " ", best_sentence).strip(" ,.-")

        # Compose intent/urgency prefix
        prefix = ""
        if config.get('emoji_friendly', False):
            emoji_map = {
                'question': '❓',
                'request': '🙏',
                'urgent': '🚨',
                'appreciation': '🙏',
                'complaint': '⚠️',
                'social': '👋',
                'follow_up': '🔄',
                'check_progress': '📊'
            }
        else:
            emoji_map = {}

        if urgency == 'critical':
            prefix = 'Urgent: '
        elif intent in ('schedule', 'meeting'):
            prefix = 'Schedule: '
        elif intent == 'request':
            prefix = 'Request: '
        elif intent == 'question':
            prefix = 'Question: '
        elif intent in ('follow_up', 'check_progress'):
            prefix = 'Follow-up: '
        elif intent == 'social':
            prefix = 'Invite: '

        summary = prebuilt_summary if prebuilt_summary is not None else (prefix + best_sentence)

        # Ensure notable time expression is carried over
        if time_phrase and time_phrase.lower() not in summary.lower():
            summary = f"{summary} {time_phrase}".strip()

        # Context cues
        if context_insights and intent in ('follow_up', 'check_progress'):
            head = context_insights[0].lower()
            if "follow-up" in head and not summary.lower().startswith("follow-up"):
                summary = "Follow-up: " + summary
            elif "continues previous" in head and not summary.lower().startswith("continuing"):
                summary = "Continuing: " + summary

        # Emoji adornment for casual platforms
        if config['emoji_friendly'] and intent in emoji_map:
            summary = emoji_map[intent] + ' ' + summary

        # Smart length control: prefer cutting at clause boundaries
        if len(summary) > max_length:
            clause_splitter = re.compile(r",|\band\b|\bbut\b", re.IGNORECASE)
            parts = clause_splitter.split(summary, maxsplit=1)
            candidate = parts[0].strip()
            if len(candidate) > max_length:
                summary = candidate[:max_length-3].rstrip() + '...'
            else:
                summary = candidate

        if config.get('casual_tone') and platform in ['whatsapp', 'slack', 'discord', 'instagram']:
            summary = summary.replace('Please', 'Pls').replace('you', 'u')

        return summary
    
    def _generate_reasoning(self, intent: str, urgency: str, context_used: bool, context_insights: List[str], platform: str) -> List[str]:
        """Generate reasoning for the analysis."""
        reasoning = []
        
        reasoning.append(f"Classified as '{intent}' intent based on message patterns and cues")
        reasoning.append(f"Urgency level: '{urgency}' based on keywords, punctuation, ALL-CAPS, and time proximity")
        reasoning.append(f"Platform-optimized for {platform}")
        
        if context_used:
            reasoning.append(f"Used conversation context ({len(context_insights)} insights)")
            for insight in context_insights[:2]:  # Show top 2 insights
                reasoning.append(f"Context: {insight}")
        else:
            reasoning.append("No conversation context available")
        
        return reasoning
    
    def _update_stats(self, user_id: str, platform: str, intent: str, urgency: str):
        """Update processing statistics."""
        self.stats['processed'] += 1
        self.stats['unique_users'].add(user_id)
        
        if platform not in self.stats['platforms']:
            self.stats['platforms'][platform] = 0
        self.stats['platforms'][platform] += 1
        
        if intent not in self.stats['intents']:
            self.stats['intents'][intent] = 0
        self.stats['intents'][intent] += 1
        
        if urgency not in self.stats['urgency_levels']:
            self.stats['urgency_levels'][urgency] = 0
        self.stats['urgency_levels'][urgency] += 1
    
    def summarize(self, message_data: Dict, use_context: bool = True) -> Dict:
        """
        Summarize a single message with context awareness.
        
        Args:
            message_data: Dictionary containing message information
            use_context: Whether to use conversation context
            
        Returns:
            Dictionary with summary and analysis results
        """
        try:
            # Extract message details
            user_id = message_data.get('user_id', 'unknown')
            platform = message_data.get('platform', 'unknown')
            message_text = message_data.get('message_text', '')
            timestamp = message_data.get('timestamp', datetime.now().isoformat())
            
            # Get context if requested
            context = []
            context_used = False
            
            if use_context:
                context = self._extract_context(user_id, platform)
                context_used = len(context) > 0
                if context_used:
                    self.stats['context_used'] += 1
            
            # Analyze message with context
            intent, intent_confidence = self._classify_intent(message_text, context)
            urgency, urgency_confidence = self._analyze_urgency(message_text, context)
            
            # Analyze context insights
            context_insights = self._analyze_context(message_data, context)
            
            # Generate summary
            summary = self._generate_summary(message_text, platform, intent, urgency, context_insights)
            
            # Determine message type
            message_type = self._determine_message_type(intent, urgency, context_insights)
            
            # Calculate overall confidence
            overall_confidence = (intent_confidence + urgency_confidence) / 2
            
            # Generate reasoning
            reasoning = self._generate_reasoning(intent, urgency, context_used, context_insights, platform)
            
            # Store message in context for future use
            self._store_message_context(message_data)
            
            # Update statistics
            self._update_stats(user_id, platform, intent, urgency)
            
            result = {
                'summary': summary,
                'type': message_type,
                'intent': intent,
                'urgency': urgency,
                'confidence': overall_confidence,
                'context_used': context_used,
                'platform_optimized': True,
                'reasoning': reasoning,
                'metadata': {
                    'intent_confidence': intent_confidence,
                    'urgency_confidence': urgency_confidence,
                    'context_messages_used': len(context),
                    'platform': platform,
                    'timestamp': timestamp,
                    'context_insights': context_insights
                }
            }
            
            logger.info(f"Summarized message for {user_id} on {platform}: {summary}")
            return result
            
        except Exception as e:
            logger.error(f"Error summarizing message: {e}")
            return {
                'summary': 'Error processing message',
                'type': 'error',
                'intent': 'unknown',
                'urgency': 'low',
                'confidence': 0.0,
                'context_used': False,
                'platform_optimized': False,
                'reasoning': [f'Error: {str(e)}'],
                'metadata': {}
            }
    
    def _determine_message_type(self, intent: str, urgency: str, context_insights: List[str]) -> str:
        """Determine message type based on intent, urgency, and context."""
        if urgency == 'critical':
            return 'urgent'
        elif intent == 'follow_up' or intent == 'check_progress':
            return 'follow-up'
        elif intent == 'question':
            return 'inquiry'
        elif intent == 'request':
            return 'request'
        elif intent == 'complaint':
            return 'complaint'
        elif intent == 'appreciation':
            return 'appreciation'
        elif intent == 'cancellation':
            return 'cancellation'
        elif intent == 'schedule':
            return 'scheduling'
        elif intent == 'sales':
            return 'sales'
        elif intent == 'delivery':
            return 'delivery'
        else:
            return 'general'
    
    def batch_summarize(self, messages: List[Dict], use_context: bool = True) -> List[Dict]:
        """
        Summarize multiple messages in batch.
        
        Args:
            messages: List of message dictionaries
            use_context: Whether to use conversation context
            
        Returns:
            List of summary results
        """
        results = []
        
        for i, message in enumerate(messages):
            result = self.summarize(message, use_context)
            results.append(result)
        
        logger.info(f"Batch summarized {len(messages)} messages")
        return results
    
    def get_user_context(self, user_id: str, platform: str) -> List[Dict]:
        """Get conversation context for a specific user and platform."""
        return self._extract_context(user_id, platform)
    
    def get_stats(self) -> Dict:
        """Get processing statistics."""
        stats = self.stats.copy()
        stats['unique_users'] = len(stats['unique_users'])
        stats['context_usage_rate'] = (stats['context_used'] / max(1, stats['processed']))
        stats['total_context_entries'] = stats['context_used']
        return stats
    
    def reset_stats(self):
        """Reset processing statistics."""
        self.stats = {
            'processed': 0,
            'context_used': 0,
            'platforms': {},
            'intents': {},
            'urgency_levels': {},
            'unique_users': set()
        }

    def export_config(self) -> Dict:
        """Export current configuration."""
        return {
            'max_context_messages': self.max_context_messages,
            'confidence_threshold': self.confidence_threshold,
            'platform_configs': self.platform_configs,
            'intent_patterns': self.intent_patterns,
            'urgency_indicators': self.urgency_indicators,
            'term_weights': self.term_weights
        }

    def update_config(self, config: Dict):
        """Update configuration."""
        if 'max_context_messages' in config:
            self.max_context_messages = config['max_context_messages']
        if 'confidence_threshold' in config:
            self.confidence_threshold = config['confidence_threshold']
        if 'platform_configs' in config:
            self.platform_configs.update(config['platform_configs'])
        if 'term_weights' in config and isinstance(config['term_weights'], dict):
            self.term_weights.update(config['term_weights'])
            self._save_learning()
    
    def receive_feedback(self, summary_id: str, feedback: str, comment: str = "", **kwargs) -> bool:
        """Receive feedback and update learning trace.
        
        Args:
            summary_id: ID of the summary being rated
            feedback: 'upvote' or 'downvote'
            comment: Optional feedback comment
            kwargs: optional fields like summary_text for weight update
        """
        try:
            summary_text = kwargs.get('summary_text', '')
            entry = {
                'summary_id': summary_id,
                'feedback': feedback,
                'comment': comment,
                'timestamp': datetime.now().isoformat(),
            }
            if summary_text:
                entry['summary_text'] = summary_text

            # Append to in-memory learning and persist
            fh = self.learning.get('feedback_history', [])
            fh.append(entry)
            # keep last 200
            self.learning['feedback_history'] = fh[-200:]

            # Update approval rate metric
            approvals = sum(1 for e in fh if e.get('feedback') == 'upvote')
            total = len(fh)
            self.learning.setdefault('performance_metrics', {})
            self.learning['performance_metrics']['approval_rate'] = approvals / total if total else 0.0

            # Update term weights from summary_text and/or comment
            def adjust_terms(text: str, delta: float):
                for w in re.findall(r"\b[\w'-]+\b", text.lower()):
                    if len(w) < 3:
                        continue
                    self.term_weights[w] = round(self.term_weights.get(w, 0.0) + delta, 4)
            if summary_text:
                adjust_terms(summary_text, 0.2 if feedback == 'upvote' else -0.2)
            if comment:
                adjust_terms(comment, 0.05 if feedback == 'upvote' else -0.05)

            self._save_learning()
            logger.info(f"Feedback received for {summary_id}: {feedback}")
            return True
        
        except Exception as e:
            logger.error(f"Error processing feedback: {e}")
            return False
    
    def get_performance_stats(self) -> Dict:
        """Get performance statistics and learning snapshot."""
        try:
            feedback_history = self.learning.get('feedback_history', [])
            approval_rate = self.learning.get('performance_metrics', {}).get('approval_rate', 0.0)
            return {
                'total_feedback': len(feedback_history),
                'approval_rate': approval_rate,
                'recent_feedback': feedback_history[-10:],
                'last_updated': datetime.now().isoformat(),
                'summarizer_metrics': {
                    'intent_keywords_count': sum(len(patterns) for patterns in self.intent_patterns.values()),
                    'urgency_patterns_count': len(self.urgency_indicators),
                    'platform_patterns_count': len(self.platform_configs),
                    'learning_terms': len(self.term_weights)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting performance stats: {e}")
            return {
                'total_feedback': 0,
                'approval_rate': 0.0,
                'recent_feedback': [],
                'error': str(e)
            }


def summarize_message(message_text: str, platform: str = 'email', user_id: str = 'default') -> Dict:
    """
    Standalone function for quick message summarization.
    
    Args:
        message_text: The message to summarize
        platform: Platform type (email, whatsapp, slack, etc.)
        user_id: User identifier
        
    Returns:
        Summary result dictionary
    """
    summarizer = SmartSummarizerV3()
    
    message = {
        'user_id': user_id,
        'platform': platform,
        'message_text': message_text,
        'timestamp': datetime.now().isoformat()
    }
    
    return summarizer.summarize(message, use_context=False)


# Example usage and testing
if __name__ == "__main__":
    # Initialize summarizer
    summarizer = SmartSummarizerV3()
    
    # Test messages with context scenario
    test_messages = [
        {
            'user_id': 'alice_work',
            'platform': 'email',
            'message_text': 'I will send the quarterly report tonight after the meeting.',
            'timestamp': '2025-08-07T09:00:00Z'
        },
        {
            'user_id': 'alice_work',
            'platform': 'email',
            'message_text': 'Hey, did the report get done?',
            'timestamp': '2025-08-07T16:45:00Z'
        },
        {
            'user_id': 'bob_friend',
            'platform': 'whatsapp',
            'message_text': 'URGENT: please reschedule the demo to tomorrow 9am!!',
            'timestamp': '2025-08-07T14:30:00Z'
        },
        {
            'user_id': 'customer_insta',
            'platform': 'instagram',
            'message_text': 'love ur latest post! 😍 where did u get that dress?',
            'timestamp': '2025-08-07T11:15:00Z'
        }
    ]
    
    # Test batch processing
    results = summarizer.batch_summarize(test_messages, use_context=True)
    
    # Display results
    for i, (message, result) in enumerate(zip(test_messages, results)):
        print(f"\n--- Message {i+1} ({message['platform']}) ---")
        print(f"Original: {message['message_text']}")
        print(f"Summary: {result['summary']}")
        print(f"Type: {result['type']} | Intent: {result['intent']} | Urgency: {result['urgency']}")
        print(f"Confidence: {result['confidence']:.2f}")
        print(f"Context Used: {result['context_used']}")
        print("Reasoning:")
        for reason in result['reasoning']:
            print(f"  - {reason}")
    
    # Show statistics
    print(f"\n--- Statistics ---")
    stats = summarizer.get_stats()
    print(f"Processed: {stats['processed']}")
