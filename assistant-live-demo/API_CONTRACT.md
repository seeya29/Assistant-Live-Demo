# Assistant Live Demo - API Contract for Frontend Integration

**Base URL:** `http://127.0.0.1:8000` (Development) | `https://your-app.vercel.app` (Production)  
**Content-Type:** `application/json`  
**For:** Yash (Frontend Developer)

## Core Message Processing Flow

```
Message → Summary → Task → Feedback
```

## 1. Submit Message for Summarization

**POST** `/api/summarize`

**Request:**
```json
{
  "user_id": "yash_frontend",
  "platform": "email",
  "conversation_id": "conv_001",
  "message_id": "msg_123",
  "message_text": "Can we schedule a review meeting next Tuesday at 3 PM?",
  "timestamp": "2025-09-18T10:00:00Z"
}
```

**Response (UI-Ready JSON):**
```json
{
  "summary_id": "s_abc123def456",
  "message_id": "msg_123",
  "summary": "User requests scheduling or rescheduling a meeting.",
  "type": "meeting",
  "intent": "meeting",
  "urgency": "low",
  "timestamp": "2025-09-18T10:00:01Z"
}
```

## 2. Convert Summary to Task

**POST** `/api/process_summary`

**Request (use summary response from step 1):**
```json
{
  "summary_id": "s_abc123def456",
  "message_id": "msg_123",
  "summary": "User requests scheduling or rescheduling a meeting.",
  "type": "meeting",
  "intent": "meeting",
  "urgency": "low",
  "timestamp": "2025-09-18T10:00:01Z"
}
```

**Response (UI-Ready JSON):**
```json
{
  "task_id": "t_xyz789abc123",
  "user_id": "yash_frontend",
  "task_summary": "Schedule review meeting next Tuesday at 3 PM",
  "task_type": "meeting",
  "scheduled_for": "2025-09-24T15:00:00Z",
  "status": "pending"
}
```

## 3. Submit User Feedback

**POST** `/api/feedback`

**Request:**
```json
{
  "summary_id": "s_abc123def456",
  "rating": "up",
  "comment": "Great summary! Very accurate.",
  "timestamp": "2025-09-18T10:05:00Z"
}
```

**Response:**
```json
{
  "success": true,
  "summary_id": "s_abc123def456",
  "timestamp": "2025-09-18T10:05:00Z"
}
```

## 4. Frontend Data Retrieval Endpoints

### Get Messages (with pagination)
**GET** `/api/messages?limit=10&offset=0`

**Response:**
```json
{
  "messages": [
    {
      "message_id": "msg_123",
      "user_id": "yash_frontend",
      "platform": "email",
      "conversation_id": "conv_001",
      "text": "Can we schedule a review meeting next Tuesday at 3 PM?",
      "timestamp": "2025-09-18T10:00:00Z"
    }
  ],
  "total": 25,
  "limit": 10,
  "offset": 0
}
```

### Get Summaries (with user filtering)
**GET** `/api/summaries?user_id=yash_frontend&limit=10&offset=0`

**Response:**
```json
{
  "summaries": [
    {
      "summary_id": "s_abc123def456",
      "message_id": "msg_123",
      "summary": "User requests scheduling or rescheduling a meeting.",
      "type": "meeting",
      "intent": "meeting",
      "urgency": "low",
      "timestamp": "2025-09-18T10:00:01Z"
    }
  ],
  "total": 15,
  "limit": 10,
  "offset": 0,
  "user_id": "yash_frontend"
}
```

### Get Tasks (with filtering)
**GET** `/api/tasks?user_id=yash_frontend&status=pending&limit=10&offset=0`

**Response:**
```json
{
  "tasks": [
    {
      "task_id": "t_xyz789abc123",
      "user_id": "yash_frontend",
      "task_summary": "Schedule review meeting next Tuesday at 3 PM",
      "task_type": "meeting",
      "scheduled_for": "2025-09-24T15:00:00Z",
      "status": "pending"
    }
  ],
  "total": 8,
  "limit": 10,
  "offset": 0,
  "user_id": "yash_frontend",
  "status": "pending"
}
```

### Get Dashboard Statistics
**GET** `/api/stats`

**Response:**
```json
{
  "totals": {
    "messages": 45,
    "summaries": 45,
    "tasks": 42,
    "feedback": 18
  },
  "task_status_distribution": {
    "pending": 35,
    "completed": 5,
    "cancelled": 2
  },
  "platform_distribution": {
    "email": 20,
    "whatsapp": 15,
    "slack": 8,
    "teams": 2
  },
  "urgency_distribution": {
    "low": 25,
    "medium": 15,
    "high": 5
  },
  "timestamp": "2025-09-18T10:30:00Z"
}
```

## 5. Task Management

### Update Task Status
**PUT** `/api/tasks/{task_id}/status`

**Request:**
```json
{
  "status": "completed"
}
```

**Response:**
```json
{
  "success": true,
  "task_id": "t_xyz789abc123",
  "new_status": "completed",
  "updated_at": "2025-09-18T10:15:00Z"
}
```

## Frontend Integration Examples

### Complete Flow in JavaScript

```javascript
const API_BASE = 'http://127.0.0.1:8000';

// Process a message through the complete pipeline
const processMessage = async (messageData) => {
  try {
    // Step 1: Summarize message
    const summaryResponse = await fetch(`${API_BASE}/api/summarize`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: messageData.userId,
        platform: messageData.platform,
        conversation_id: messageData.conversationId,
        message_id: `msg_${Date.now()}`,
        message_text: messageData.text,
        timestamp: new Date().toISOString()
      })
    });
    
    if (!summaryResponse.ok) {
      throw new Error(`Summary failed: ${summaryResponse.status}`);
    }
    
    const summary = await summaryResponse.json();
    
    // Step 2: Create task from summary
    const taskResponse = await fetch(`${API_BASE}/api/process_summary`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(summary)
    });
    
    if (!taskResponse.ok) {
      throw new Error(`Task creation failed: ${taskResponse.status}`);
    }
    
    const task = await taskResponse.json();
    
    return {
      success: true,
      summary,
      task
    };
    
  } catch (error) {
    console.error('Message processing failed:', error);
    return {
      success: false,
      error: error.message
    };
  }
};

// Load dashboard data
const loadDashboardData = async () => {
  try {
    const [messagesRes, summariesRes, tasksRes, statsRes] = await Promise.all([
      fetch(`${API_BASE}/api/messages?limit=10`),
      fetch(`${API_BASE}/api/summaries?limit=10`),
      fetch(`${API_BASE}/api/tasks?status=pending&limit=10`),
      fetch(`${API_BASE}/api/stats`)
    ]);
    
    const data = {
      messages: await messagesRes.json(),
      summaries: await summariesRes.json(),
      tasks: await tasksRes.json(),
      stats: await statsRes.json()
    };
    
    return data;
  } catch (error) {
    console.error('Dashboard data loading failed:', error);
    throw error;
  }
};

// Submit feedback
const submitFeedback = async (summaryId, rating, comment = null) => {
  try {
    const response = await fetch(`${API_BASE}/api/feedback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        summary_id: summaryId,
        rating: rating, // 'up' or 'down'
        comment: comment,
        timestamp: new Date().toISOString()
      })
    });
    
    if (!response.ok) {
      throw new Error(`Feedback submission failed: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Feedback submission failed:', error);
    throw error;
  }
};
```

## Data Types and Validation

### Supported Platforms
```javascript
const PLATFORMS = [
  'whatsapp', 'instagram', 'email', 'slack', 
  'teams', 'telegram', 'discord'
];
```

### Summary Types
```javascript
const SUMMARY_TYPES = ['follow-up', 'meeting', 'request'];
```

### Urgency Levels
```javascript
const URGENCY_LEVELS = ['low', 'medium', 'high'];
```

### Task Types
```javascript
const TASK_TYPES = ['meeting', 'reminder', 'follow-up'];
```

### Task Status Options
```javascript
const TASK_STATUSES = ['pending', 'completed', 'cancelled'];
```

## Error Handling

### Standard Error Response Format
```json
{
  "detail": "Error description",
  "status_code": 400
}
```

### Common HTTP Status Codes
- `200` - Success
- `400` - Bad Request (invalid data format)
- `404` - Not Found (invalid ID)
- `422` - Validation Error (invalid enum values)
- `500` - Internal Server Error

### Error Handling Example
```javascript
const handleApiError = async (response) => {
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(`API Error ${response.status}: ${errorData.detail}`);
  }
  return response.json();
};
```

## Testing and Development

### Health Check
**GET** `/api/health`

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2025-09-18T10:00:00Z"
}
```

### Sample Data Setup
```bash
# Start API
uvicorn assistant_api.main:app --reload --port 8000

# Populate with sample data
python seed_data.py

# Run end-to-end tests
python test_e2e_flow.py
```

### Quick Test Commands
```bash
# Health check
curl http://127.0.0.1:8000/api/health

# Get statistics
curl http://127.0.0.1:8000/api/stats

# Test message processing
curl -X POST "http://127.0.0.1:8000/api/summarize" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "platform": "email",
    "conversation_id": "test_conv",
    "message_id": "test_msg_1",
    "message_text": "Can we schedule a meeting tomorrow?",
    "timestamp": "2025-09-18T10:00:00Z"
  }'
```

---

**Ready for Frontend Development!**  
**Contact:** Sankalp (Backend/API)  
**Updated:** September 2025

This API contract provides everything needed for building the Streamlit UI with real-time data integration.