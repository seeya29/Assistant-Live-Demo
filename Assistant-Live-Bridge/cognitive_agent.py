import json
import re
from datetime import datetime
import random
from collections import defaultdict, Counter
from typing import Any, Dict, Optional, Tuple, Set


class CognitiveAgent:
    """
    CognitiveAgent with:
      - Lightweight NLP heuristics for intent and urgency detection
      - Feedback-driven improvement trace
      - Input normalization to avoid hardcoded platform fields
      - Queue integration hooks (adapter pattern)
    """

    URGENCY_KEYWORDS = {
        'urgent', 'asap', 'immediately', 'now', 'right away', 'priority', 'important',
        'critical', 'blocker', 'p0', 'p1', 'high priority', 'time sensitive', 'rush', 'expedite',
        'deadline', 'overdue', 'escalate', 'eod', 'eow', 'today', 'tomorrow', 'tonight'
    }

    INTENT_KEYWORDS = {
        'support': {
            'issue', 'bug', 'error', 'help', 'not working', 'broken', 'fail', 'failing',
            'troubleshoot', 'crash', 'blocked', 'investigate', 'fix', 'support', 'incident'
        },
        'billing': {
            'invoice', 'payment', 'refund', 'billing', 'charge', 'credit card', 'paid', 'receipt',
            'quote', 'pricing', 'cost', 'renewal', 'subscription', 'trial'
        },
        'meeting': {
            'meeting', 'schedule', 'reschedule', 'calendar', 'call', 'zoom', 'teams', 'invite',
            'availability', 'slot', 'time', 'sync', 'standup', 'retro', 'catch up'
        },
        'status': {
            'status', 'update', 'progress', 'eta', 'follow up', 'follow-up', 'fyi', 'heads up',
            'summary', 'report'
        },
        'sales': {
            'demo', 'trial', 'feature', 'capability', 'evaluation', 'buy', 'purchase', 'order',
            'discount', 'deal', 'offer'
        },
        'spam': {
            'win', 'lottery', 'prize', 'free money', 'viagra', 'casino', 'crypto', 'investment',
            'million', 'billion', 'wire', 'inherit', 'nigerian', 'forex', 'binary options', 'pump'
        },
        'newsletter': {
            'newsletter', 'digest', 'update', 'announcement', 'release notes', 'blog', 'weekly'
        }
    }

    DEADLINE_REGEXPS = [
        re.compile(r"\bby\s+(?:eod|eow|tomorrow|today|tonight|monday|tuesday|wednesday|thursday|friday)\b", re.I),
        re.compile(r"\bby\s+\d{4}-\d{2}-\d{2}\b", re.I),
        re.compile(r"\bby\s+\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+\b", re.I),
        re.compile(r"\b(in|within)\s+\d+\s+(min|mins|minutes|hour|hours|day|days|week|weeks)\b", re.I),
    ]

    TIME_OF_DAY_BUCKETS = [
        (0, 6, 'night'), (6, 12, 'morning'), (12, 18, 'afternoon'), (18, 24, 'evening')
    ]

    def __init__(self, learning_rate: float = 0.1, discount_factor: float = 0.95, epsilon: float = 0.1, queue_client: Any = None):
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon
        self.queue_client = queue_client

        # Q-table for reinforcement learning
        self.q_table: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

        # Memory for sender patterns and keywords
        self.sender_memory: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'action_counts': Counter(),
            'total_emails': 0,
            'avg_confidence': 0.0,
            'last_interaction': None
        })

        # Keyword memory
        self.keyword_memory: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'action_counts': Counter(),
            'confidence_scores': []
        })

        # Subject-topic relationships (reserved for future use)
        self.topic_memory: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'action_counts': Counter(),
            'keywords': set(),
            'confidence_scores': []
        })

        # Available actions
        self.actions = ['Reply', 'Archive', 'Forward', 'Mark Important', 'Delete', 'Spam']

        # Feedback history with improvement trace
        self.feedback_history: list[Dict[str, Any]] = []

        # Load existing data if available
        self.load_memory()

    # ----------------------------- Normalization ----------------------------- #
    def normalize_input(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize heterogeneous payloads to a canonical schema without
        assuming a specific platform.

        Canonical fields returned:
          - sender: str
          - subject: str
          - body: str
          - timestamp: iso str or None
          - platform: optional str
          - metadata: dict of passthrough fields
        """
        metadata = dict(raw)
        platform = raw.get('platform') or raw.get('source') or raw.get('provider')

        # Email-like payloads
        sender = raw.get('sender') or raw.get('from') or raw.get('user') or raw.get('author') or raw.get('email') or ''
        subject = raw.get('subject') or raw.get('title') or raw.get('topic') or ''
        body = raw.get('body') or raw.get('text') or raw.get('message') or raw.get('content') or raw.get('snippet') or ''

        # Slack/Chat-like: prefer text for subject if no subject available
        if not subject and body:
            # Use first 80 chars as pseudo-subject for ranking
            subject = body[:80]

        # Timestamp extraction
        ts = raw.get('timestamp') or raw.get('ts') or raw.get('date') or raw.get('created_at') or raw.get('received_at')
        if isinstance(ts, (int, float)):
            try:
                ts = datetime.fromtimestamp(ts).isoformat()
            except Exception:
                ts = None
        elif isinstance(ts, str) and re.match(r"^\d{10}(?:\.\d+)?$", ts):
            try:
                ts = datetime.fromtimestamp(float(ts)).isoformat()
            except Exception:
                ts = None
        elif isinstance(ts, str):
            # try to keep as-is if it looks like ISO
            ts = ts
        else:
            ts = None

        return {
            'sender': str(sender).strip().lower(),
            'subject': str(subject).strip(),
            'body': str(body).strip(),
            'timestamp': ts,
            'platform': platform,
            'metadata': metadata,
        }

    # -------------------------- Feature Engineering ------------------------- #
    def _time_of_day_bucket(self, dt: Optional[datetime] = None) -> str:
        dt = dt or datetime.now()
        h = dt.hour
        for start, end, label in self.TIME_OF_DAY_BUCKETS:
            if start <= h < end:
                return label
        return 'unknown'

    def _detect_deadline(self, text: str) -> bool:
        for rx in self.DEADLINE_REGEXPS:
            if rx.search(text):
                return True
        return False

    def _urgency_score(self, text: str) -> Tuple[float, Dict[str, Any]]:
        """Return urgency score in [0,1] and contributing signals."""
        t = text.lower()
        signals = {}

        # Keyword hits
        kw_hits = sum(1 for k in self.URGENCY_KEYWORDS if k in t)
        signals['keyword_hits'] = kw_hits
        score = min(0.6, kw_hits * 0.12)  # up to 0.6 from keywords

        # Exclamations
        exclam = t.count('!')
        signals['exclam'] = exclam
        score += min(0.15, exclam * 0.05)

        # All-caps words (simple heuristic)
        caps_words = re.findall(r"\b[A-Z]{3,}\b", text)
        signals['caps_words'] = len(caps_words)
        score += min(0.1, len(caps_words) * 0.03)

        # Time expressions
        time_expr = any(rx.search(t) for rx in self.DEADLINE_REGEXPS)
        signals['time_expr'] = time_expr
        if time_expr:
            score += 0.15

        return min(1.0, score), signals

    def _detect_intent(self, text: str) -> Tuple[str, Dict[str, float]]:
        t = text.lower()
        scores: Dict[str, float] = {}
        for intent, kws in self.INTENT_KEYWORDS.items():
            hits = sum(1 for k in kws if k in t)
            # weight longer keywords slightly higher
            weight = sum((min(len(k), 15) / 15.0) for k in kws if k in t)
            scores[intent] = hits * 0.4 + weight * 0.6
        # Normalize
        total = sum(scores.values()) or 1.0
        norm = {k: v / total for k, v in scores.items()}
        intent = max(norm, key=norm.get)
        return intent, norm

    def extract_features(self, email_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Set[str]]:
        """Extract features from (normalized) input for state representation."""
        data = self.normalize_input(email_data)
        sender = data['sender']
        subject = data['subject']
        body = data['body']
        combined_text = f"{subject}\n{body}"

        # Extract simple keywords
        words = re.findall(r"[A-Za-z']+", combined_text.lower())
        keywords = {w for w in words if len(w) > 3}

        # Heuristics
        urgency, urgency_signals = self._urgency_score(combined_text)
        has_deadline = self._detect_deadline(combined_text)
        has_question = '?' in subject or '?' in body
        intent, intent_scores = self._detect_intent(combined_text)

        # Create state representation
        state = {
            'sender': sender,
            'subject_length': len(subject),
            'body_length': len(body),
            'has_urgent_words': urgency >= 0.35,
            'urgency_score': round(urgency, 3),
            'has_deadline': has_deadline,
            'has_question': has_question,
            'intent': intent,
            'intent_scores': intent_scores,
            'sender_frequency': self.sender_memory[sender]['total_emails'],
            'time_of_day': self._time_of_day_bucket(),
            'urgency_signals': urgency_signals,
            'platform': data.get('platform'),
        }
        return state, keywords

    def get_state_key(self, state: Dict[str, Any]) -> str:
        """Convert state to a compact string key for Q-table."""
        urgency_bucket = int(state['urgency_score'] * 3)  # 0..3
        return f"{state['sender']}|{state['intent']}|u{urgency_bucket}|q{int(state['has_question'])}|{state['time_of_day']}"

    # ----------------------------- Policy / Action --------------------------- #
    def predict_action(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Predict action using epsilon-greedy policy with heuristic biases."""
        state, keywords = self.extract_features(email_data)
        state_key = self.get_state_key(state)
        sender = state['sender']

        # Sender memory bias
        if sender in self.sender_memory and self.sender_memory[sender]['total_emails'] > 5:
            most_common_action = self.sender_memory[sender]['action_counts'].most_common(1)
            if most_common_action:
                sender_bias_action = most_common_action[0][0]
                sender_bias_bonus = 0.3
            else:
                sender_bias_action = None
                sender_bias_bonus = 0.0
        else:
            sender_bias_action = None
            sender_bias_bonus = 0.0

        # Epsilon-greedy
        if random.random() < self.epsilon:
            action = random.choice(self.actions)
        else:
            # Base Q-values
            q_values = {a: self.q_table[state_key][a] for a in self.actions}

            # Heuristic biases
            heuristic_bias = {a: 0.0 for a in self.actions}

            # Urgency
            if state['urgency_score'] >= 0.6:
                heuristic_bias['Reply'] += 0.4
                heuristic_bias['Mark Important'] += 0.3
            elif state['urgency_score'] >= 0.35:
                heuristic_bias['Reply'] += 0.2

            # Intent-specific nudges
            intent = state['intent']
            if intent == 'support':
                heuristic_bias['Reply'] += 0.3
            elif intent == 'billing':
                heuristic_bias['Reply'] += 0.2
                heuristic_bias['Mark Important'] += 0.2
            elif intent == 'meeting':
                heuristic_bias['Reply'] += 0.2
            elif intent == 'newsletter':
                heuristic_bias['Archive'] += 0.3
            elif intent == 'spam':
                heuristic_bias['Spam'] += 0.6
                heuristic_bias['Delete'] += 0.2

            # Questions often require reply
            if state['has_question']:
                heuristic_bias['Reply'] += 0.25

            # Sender bias
            if sender_bias_action:
                heuristic_bias[sender_bias_action] += 0.5

            # Apply biases
            for a in self.actions:
                q_values[a] += heuristic_bias[a]

            action = max(q_values, key=q_values.get)

        # Confidence
        confidence = self.calculate_confidence(state, action, keywords, sender_bias_bonus)

        # Explanation
        explanation = self.generate_explanation(state, action, keywords, sender)

        return {
            'action': action,
            'confidence': confidence,
            'explanation': explanation,
            'state': state,
            'keywords': list(keywords)
        }

    def calculate_confidence(self, state: Dict[str, Any], action: str, keywords: Set[str], confidence_bonus: float) -> float:
        """Calculate confidence score for the predicted action."""
        base_confidence = 0.5

        # Sender-based confidence
        sender = state['sender']
        if sender in self.sender_memory:
            sender_data = self.sender_memory[sender]
            if sender_data['total_emails'] > 0:
                action_frequency = sender_data['action_counts'][action] / max(1, sender_data['total_emails'])
                base_confidence += action_frequency * 0.25

        # Keyword-based confidence
        keyword_confidence = 0.0
        for keyword in keywords:
            if keyword in self.keyword_memory and self.keyword_memory[keyword]['action_counts'][action] > 0:
                keyword_confidence += 0.05

        # State-based confidence
        if state['urgency_score'] >= 0.6 and action in ['Reply', 'Mark Important']:
            base_confidence += 0.2
        if state['has_question'] and action == 'Reply':
            base_confidence += 0.2
        if state['intent'] == 'spam' and action in ['Spam', 'Delete']:
            base_confidence += 0.15
        if state['intent'] == 'newsletter' and action == 'Archive':
            base_confidence += 0.1

        final_confidence = min(0.98, base_confidence + keyword_confidence + confidence_bonus)
        return round(max(0.01, final_confidence), 3)

    def generate_explanation(self, state: Dict[str, Any], action: str, keywords: Set[str], sender: str) -> str:
        """Generate human-readable explanation for the action."""
        explanations = []

        # Sender-based explanation
        if sender in self.sender_memory and self.sender_memory[sender]['total_emails'] > 3:
            most_common = self.sender_memory[sender]['action_counts'].most_common(1)
            if most_common and most_common[0][0] == action:
                explanations.append(f"Sender pattern: previously {most_common[0][1]}x '{action}'")

        # State-based explanations
        if state['urgency_score'] >= 0.6:
            explanations.append("High urgency signals detected")
        elif state['urgency_score'] >= 0.35:
            explanations.append("Moderate urgency signals detected")
        if state['has_deadline']:
            explanations.append("Contains a deadline/time expression")
        if state['has_question']:
            explanations.append("Contains a question")
        if state['subject_length'] > 50:
            explanations.append("Long subject suggests detailed content")

        # Intent
        explanations.append(f"Detected intent: {state['intent']}")

        # Keyword-based explanations
        if keywords:
            relevant_keywords = [k for k in keywords if k in self.keyword_memory]
            if relevant_keywords:
                explanations.append(f"Known keywords: {', '.join(sorted(relevant_keywords)[:3])}")

        if not explanations:
            explanations.append("Based on general message patterns")

        return "; ".join(explanations)

    # ------------------------------ Feedback/Learning ------------------------ #
    def receive_feedback(self, email_data: Dict[str, Any], predicted_action: str, user_feedback: str, correct_action: Optional[str] = None) -> Dict[str, Any]:
        """
        Receive feedback and update Q-table and memory.
        user_feedback: one of {'approve','reject','up','down','👍','👎'}
        correct_action: if provided for 'reject', use this as the true action
        """
        # Normalize feedback values
        normalized_feedback = {
            'approve': 'approve', 'up': 'approve', '👍': 'approve', 'thumbs_up': 'approve', True: 'approve',
            'reject': 'reject', 'down': 'reject', '👎': 'reject', 'thumbs_down': 'reject', False: 'reject'
        }.get(user_feedback, 'neutral')

        state, keywords = self.extract_features(email_data)
        state_key = self.get_state_key(state)
        sender = state['sender']

        # Determine reward
        if normalized_feedback == 'approve':
            reward = 2.0
            final_action = predicted_action
        elif normalized_feedback == 'reject':
            reward = -2.0
            final_action = correct_action if correct_action else predicted_action
        else:
            reward = 0.0
            final_action = predicted_action

        # Update Q-table (SARSA-style single-step update)
        prev_q = self.q_table[state_key][predicted_action]
        max_future_q = max([self.q_table[state_key][a] for a in self.actions] or [0.0])
        new_q = prev_q + self.learning_rate * (reward + self.discount_factor * max_future_q - prev_q)
        self.q_table[state_key][predicted_action] = new_q

        # Update sender memory
        before_sender_count = self.sender_memory[sender]['action_counts'][final_action]
        self.sender_memory[sender]['action_counts'][final_action] += 1
        self.sender_memory[sender]['total_emails'] += 1
        self.sender_memory[sender]['last_interaction'] = datetime.now().isoformat()
        after_sender_count = self.sender_memory[sender]['action_counts'][final_action]

        # Update keyword memory
        updated_keywords = []
        for keyword in keywords:
            before_kw = self.keyword_memory[keyword]['action_counts'][final_action]
            self.keyword_memory[keyword]['action_counts'][final_action] += 1
            self.keyword_memory[keyword]['confidence_scores'].append(reward)
            after_kw = self.keyword_memory[keyword]['action_counts'][final_action]
            if after_kw != before_kw:
                updated_keywords.append({'keyword': keyword, 'before': before_kw, 'after': after_kw})

        # Log feedback with improvement trace details
        feedback_entry = {
            'timestamp': datetime.now().isoformat(),
            'sender': sender,
            'subject': email_data.get('subject') or email_data.get('title') or '',
            'predicted_action': predicted_action,
            'user_feedback': normalized_feedback,
            'correct_action': final_action,
            'reward': reward,
            'confidence': self.calculate_confidence(state, predicted_action, keywords, 0.0),
            'trace': {
                'state_key': state_key,
                'prev_q': round(prev_q, 4),
                'new_q': round(new_q, 4),
                'delta_q': round(new_q - prev_q, 4),
                'sender_action_count_before': before_sender_count,
                'sender_action_count_after': after_sender_count,
                'updated_keywords': updated_keywords,
                'intent': state['intent'],
                'urgency_score': state['urgency_score'],
            }
        }
        self.feedback_history.append(feedback_entry)

        # Save memory
        self.save_memory()

        return feedback_entry

    def get_improvement_trace(self, limit: int = 20):
        """Return the last N feedback entries with traces."""
        return self.feedback_history[-limit:]

    # ------------------------------- Statistics ------------------------------ #
    def get_statistics(self) -> Dict[str, Any]:
        """Get agent statistics for dashboard."""
        total_feedback = len(self.feedback_history)
        if total_feedback == 0:
            return {
                'total_feedback': 0,
                'approval_rate': 0.0,
                'avg_confidence': 0.0,
                'top_actions': [],
                'top_senders': [],
                'recent_performance': []
            }

        approvals = sum(1 for f in self.feedback_history if f.get('user_feedback') == 'approve')
        approval_rate = approvals / total_feedback if total_feedback else 0.0

        confidences = [f.get('confidence', 0.0) for f in self.feedback_history]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        action_counts = Counter([f.get('correct_action') for f in self.feedback_history])
        top_actions = action_counts.most_common(5)

        sender_counts = Counter([f.get('sender') for f in self.feedback_history])
        top_senders = sender_counts.most_common(5)

        recent_feedback = self.feedback_history[-10:]
        recent_performance = []
        for f in recent_feedback:
            recent_performance.append({
                'timestamp': f.get('timestamp'),
                'reward': f.get('reward'),
                'confidence': f.get('confidence')
            })

        return {
            'total_feedback': total_feedback,
            'approval_rate': round(approval_rate, 3),
            'avg_confidence': round(avg_confidence, 3),
            'top_actions': top_actions,
            'top_senders': top_senders,
            'recent_performance': recent_performance
        }

    # ----------------------------- Persistence ------------------------------ #
    def save_memory(self):
        """Save agent memory to file."""
        memory_data = {
            'q_table': {k: dict(v) for k, v in self.q_table.items()},
            'sender_memory': {k: {
                'action_counts': dict(v.get('action_counts', {})),
                'total_emails': v.get('total_emails', 0),
                'avg_confidence': v.get('avg_confidence', 0.0),
                'last_interaction': v.get('last_interaction')
            } for k, v in self.sender_memory.items()},
            'keyword_memory': {k: {
                'action_counts': dict(v.get('action_counts', {})),
                'confidence_scores': list(v.get('confidence_scores', []))
            } for k, v in self.keyword_memory.items()},
            'topic_memory': {k: {
                'action_counts': dict(v.get('action_counts', {})),
                'keywords': list(v.get('keywords', set())),
                'confidence_scores': list(v.get('confidence_scores', []))
            } for k, v in self.topic_memory.items()},
            'feedback_history': self.feedback_history
        }

        with open('agent_memory.json', 'w', encoding='utf-8') as f:
            json.dump(memory_data, f, indent=2, ensure_ascii=False)

    def load_memory(self):
        """Load agent memory from file if present."""
        try:
            with open('agent_memory.json', 'r', encoding='utf-8') as f:
                memory_data = json.load(f)
        except FileNotFoundError:
            return

        # Q-table
        self.q_table = defaultdict(lambda: defaultdict(float))
        for state, actions in memory_data.get('q_table', {}).items():
            for action, value in actions.items():
                self.q_table[state][action] = value

        # Sender memory
        self.sender_memory = defaultdict(lambda: {
            'action_counts': Counter(),
            'total_emails': 0,
            'avg_confidence': 0.0,
            'last_interaction': None
        })
        for sender, data in memory_data.get('sender_memory', {}).items():
            self.sender_memory[sender] = {
                'action_counts': Counter(data.get('action_counts', {})),
                'total_emails': data.get('total_emails', 0),
                'avg_confidence': data.get('avg_confidence', 0.0),
                'last_interaction': data.get('last_interaction')
            }

        # Keyword memory
        self.keyword_memory = defaultdict(lambda: {
            'action_counts': Counter(),
            'confidence_scores': []
        })
        for keyword, data in memory_data.get('keyword_memory', {}).items():
            self.keyword_memory[keyword] = {
                'action_counts': Counter(data.get('action_counts', {})),
                'confidence_scores': list(data.get('confidence_scores', []))
            }

        # Topic memory
        self.topic_memory = defaultdict(lambda: {
            'action_counts': Counter(),
            'keywords': set(),
            'confidence_scores': []
        })
        for topic, data in memory_data.get('topic_memory', {}).items():
            self.topic_memory[topic] = {
                'action_counts': Counter(data.get('action_counts', {})),
                'keywords': set(data.get('keywords', [])),
                'confidence_scores': list(data.get('confidence_scores', []))
            }

        # Feedback history
        self.feedback_history = memory_data.get('feedback_history', [])

    # ----------------------------- Queue Integration ------------------------ #
    def set_queue_client(self, queue_client: Any):
        """Attach/replace a queue client that implements `get_next` and `post_result`."""
        self.queue_client = queue_client

    def process_queue_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single queue item and return a structured decision payload.
        Expected queue item is a dict with arbitrary fields; they are normalized.
        """
        decision = self.predict_action(item)
        result = {
            'input': self.normalize_input(item),
            'decision': {
                'action': decision['action'],
                'confidence': decision['confidence'],
                'explanation': decision['explanation'],
                'state': decision['state']
            }
        }
        return result

    def run_queue_once(self) -> Optional[Dict[str, Any]]:
        """
        Pull a single item from the attached queue, process it, and optionally post result.
        The queue client is expected to offer:
          - get_next() -> Optional[Dict]
          - post_result(item: Dict, result: Dict) -> None
        """
        if not self.queue_client:
            return None
        item = self.queue_client.get_next()
        if not item:
            return None
        result = self.process_queue_item(item)
        try:
            self.queue_client.post_result(item, result)
        except Exception:
            # Allow silent failures to avoid hard dependency on queue impl
            pass
        return result
