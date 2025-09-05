# Database Schema Documentation

This document defines the database schema for the integrated SmartBrief v3 + Daily Cognitive Agent system.

## Database Collections

### 1. Messages Collection

Stores raw incoming messages from various platforms.

```json
{
  "_id": "ObjectId",
  "user_id": "string",
  "platform": "string", // email, whatsapp, instagram, telegram, slack
  "message_text": "string",
  "timestamp": "ISO 8601 datetime string",
  "message_id": "string", // unique identifier from platform
  "metadata": {
    "sender": "string",
    "subject": "string", // for email
    "message_type": "string", // original type if available
    "raw_data": "object" // platform-specific raw data
  },
  "created_at": "ISO 8601 datetime string",
  "updated_at": "ISO 8601 datetime string"
}
```

**Indexes:**
- `user_id` (ascending)
- `platform` (ascending)
- `timestamp` (descending)
- `message_id` (unique)

### 2. Summaries Collection

Stores processed summaries with intent and urgency analysis from SmartBrief v3.

```json
{
  "_id": "ObjectId",
  "summary_id": "string", // unique identifier for this summary
  "message_id": "string", // reference to messages collection
  "user_id": "string",
  "platform": "string",
  "summary": "string",
  "intent": "string",
  "urgency": "string", // low, medium, high, critical
  "type": "string", // meeting, reminder, follow-up, urgent, info, action_required
  "confidence": "float", // 0.0 to 1.0
  "reasoning": "array of strings",
  "context_used": "boolean",
  "feedback": {
    "rating": "string", // upvote, downvote, neutral
    "comment": "string",
    "feedback_timestamp": "ISO 8601 datetime string"
  },
  "processing_metadata": {
    "model_version": "string",
    "processing_time_ms": "integer",
    "context_data": "object"
  },
  "created_at": "ISO 8601 datetime string",
  "updated_at": "ISO 8601 datetime string"
}
```

**Indexes:**
- `summary_id` (unique)
- `message_id` (ascending)
- `user_id` (ascending)
- `urgency` (ascending)
- `intent` (ascending)
- `created_at` (descending)

### 3. Tasks Collection

Stores actionable tasks created by the Cognitive Agent from processed summaries.

```json
{
  "_id": "ObjectId",
  "task_id": "string", // unique identifier for this task
  "summary_id": "string", // reference to summaries collection
  "user_id": "string",
  "platform": "string",
  "task_summary": "string",
  "task_type": "string", // meeting, reminder, follow-up, urgent, info, action_required
  "scheduled_for": "ISO 8601 datetime string", // null if no schedule
  "status": "string", // pending, in_progress, completed, cancelled, missed
  "priority": "string", // low, medium, high, critical
  "context_score": "float", // 0.0 to 1.0
  "recommendations": [
    {
      "action": "string",
      "description": "string",
      "priority": "string",
      "completed": "boolean",
      "completed_at": "ISO 8601 datetime string"
    }
  ],
  "original_message": "string",
  "cognitive_metadata": {
    "classification_confidence": "float",
    "scheduling_confidence": "float",
    "agent_version": "string"
  },
  "completion_data": {
    "completed_at": "ISO 8601 datetime string",
    "completion_method": "string", // manual, automatic, timeout
    "user_feedback": "string"
  },
  "created_at": "ISO 8601 datetime string",
  "updated_at": "ISO 8601 datetime string"
}
```

**Indexes:**
- `task_id` (unique)
- `summary_id` (ascending)
- `user_id` (ascending)
- `status` (ascending)
- `priority` (ascending)
- `scheduled_for` (ascending)
- `created_at` (descending)

## Relationships

1. **Messages → Summaries**: One-to-One
   - Each message generates exactly one summary
   - `summaries.message_id` references `messages.message_id`

2. **Summaries → Tasks**: One-to-One
   - Each summary generates exactly one task
   - `tasks.summary_id` references `summaries.summary_id`

3. **User Context**: All collections are linked by `user_id`

## Database Choice

### MongoDB (Recommended)
- Better for flexible schema evolution
- Native JSON document storage
- Excellent for analytics and aggregation
- Easy horizontal scaling

### PostgreSQL (Alternative)
- ACID compliance
- Complex queries with joins
- Better for strict data consistency
- JSON column support for metadata

## Environment Configuration

```env
# MongoDB Configuration
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DATABASE=smartbrief_cognitive_agent

# PostgreSQL Configuration (if used instead)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=smartbrief_cognitive_agent
POSTGRES_USER=username
POSTGRES_PASSWORD=password

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=true
```

## Migration Scripts

Future schema changes should be handled through migration scripts:

- `migrations/001_initial_schema.py`
- `migrations/002_add_feedback_fields.py`
- etc.

## Data Retention

- **Messages**: Retain for 1 year
- **Summaries**: Retain for 2 years (for ML training)
- **Tasks**: Retain completed tasks for 6 months, pending tasks indefinitely