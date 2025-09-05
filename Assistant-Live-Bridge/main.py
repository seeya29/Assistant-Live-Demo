"""
Main FastAPI Application - Central entry point for the integrated SmartBrief v3 + Daily Cognitive Agent system.
Provides the three main endpoints: /summarize, /process_summary, and /feedback.
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
import uvicorn

from smart_summarizer_api import get_summarizer_api, close_summarizer_api
from cognitive_agent_api import get_cognitive_agent_api, close_cognitive_agent_api
from database_config import test_database_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Force working directory to the project base so all relative paths resolve correctly
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    os.chdir(BASE_DIR)
except Exception:
    pass

# Security and CORS configuration
API_KEY = os.getenv("API_KEY")
API_REQUIRE_KEY = os.getenv("API_REQUIRE_KEY", "false").lower() == "true"
ALLOWED_ORIGINS_ENV = os.getenv("ALLOWED_ORIGINS", "*")

# Simple in-process metrics
_metrics = {
    "total_requests": 0,
    "per_endpoint": {}
}

# Pydantic models for request/response validation
class MessageInput(BaseModel):
    """Input model for /summarize endpoint."""
    user_id: str = Field(..., description="Unique identifier for the user")
    platform: str = Field(..., description="Source platform (free-form)")
    message_text: str = Field(..., min_length=1, max_length=10000, description="The message content")
    timestamp: str = Field(..., description="ISO 8601 timestamp of the message")
    message_id: Optional[str] = Field(None, description="Optional unique message identifier")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional additional metadata")
    
    @validator('platform')
    def normalize_platform(cls, v):
        return str(v).strip().lower()
    
    @validator('timestamp')
    def validate_timestamp(cls, v):
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError('Invalid timestamp format. Use ISO 8601 format.')
        return v

class SummaryInput(BaseModel):
    """Input model for /process_summary endpoint."""
    summary_id: Optional[str] = Field(None, description="Summary identifier from /summarize endpoint")
    user_id: str = Field(..., description="Unique identifier for the user")
    platform: str = Field(..., description="Source platform")
    summary: str = Field(..., min_length=1, description="The summary text")
    intent: str = Field(..., description="Detected intent")
    urgency: str = Field(..., description="Urgency level (low, medium, high, critical)")
    type: Optional[str] = Field(None, description="Message type")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score")
    reasoning: Optional[List[str]] = Field(None, description="Reasoning for the analysis")
    context_used: Optional[bool] = Field(False, description="Whether context was used")
    original_message: Optional[str] = Field(None, description="Original message text")
    
    @validator('platform')
    def normalize_platform(cls, v):
        return str(v).strip().lower()
    
    @validator('urgency')
    def validate_urgency(cls, v):
        valid_urgencies = ['low', 'medium', 'high', 'critical']
        if v not in valid_urgencies:
            raise ValueError(f'Urgency must be one of: {", ".join(valid_urgencies)}')
        return v

class FeedbackInput(BaseModel):
    """Input model for /feedback endpoint."""
    summary_id: str = Field(..., description="Summary identifier to provide feedback for")
    feedback: str = Field(..., description="Feedback type (upvote or downvote)")
    comment: Optional[str] = Field(None, max_length=1000, description="Optional feedback comment")
    
    @validator('feedback')
    def validate_feedback(cls, v):
        if v not in ['upvote', 'downvote']:
            raise ValueError('Feedback must be either "upvote" or "downvote"')
        return v

class StandardResponse(BaseModel):
    """Standard response model."""
    success: bool
    message: Optional[str] = None
    timestamp: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_type: Optional[str] = None

# Lifespan manager for startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    # Startup
    logger.info("Starting SmartBrief v3 + Cognitive Agent API...")

    # Ensure required local folders exist (prevents FileNotFoundError for contexts)
    try:
        os.makedirs(os.path.join(BASE_DIR, 'user_contexts'), exist_ok=True)
    except Exception:
        pass
    
    # Test database connection
    if not test_database_connection():
        logger.error("Database connection test failed!")
        raise RuntimeError("Database connection failed")
    
    # Initialize API components
    try:
        summarizer_api = get_summarizer_api()
        cognitive_api = get_cognitive_agent_api()
        logger.info("API components initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize API components: {str(e)}")
        raise RuntimeError(f"Component initialization failed: {str(e)}")
    
    logger.info("API startup completed successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down API...")
    close_summarizer_api()
    close_cognitive_agent_api()
    logger.info("API shutdown completed")

# Create FastAPI application
app = FastAPI(
    title="SmartBrief v3 + Daily Cognitive Agent API",
    description="Integrated API for message summarization, intent analysis, and task creation",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
allowed_origins = ["*"] if ALLOWED_ORIGINS_ENV.strip() == "*" else [o.strip() for o in ALLOWED_ORIGINS_ENV.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def security_and_metrics_middleware(request: Request, call_next):
    # Metrics collection
    path = request.url.path
    _metrics["total_requests"] += 1
    _metrics["per_endpoint"][path] = _metrics["per_endpoint"].get(path, 0) + 1

    # API key enforcement (optional)
    if API_REQUIRE_KEY:
        # Allow unauthenticated access to health and GET docs/static
        if not (path.startswith("/health") or path.startswith("/v1/health") or request.method == "GET"):
            if request.headers.get("x-api-key") != API_KEY:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid API key"}
                )
    response = await call_next(request)
    return response

# Root endpoint
@app.get("/", response_model=Dict[str, Any])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "SmartBrief v3 + Daily Cognitive Agent API",
        "version": "1.0.0",
        "endpoints": {
            "/summarize": "POST - Process messages into summaries with intent analysis",
            "/process_summary": "POST - Convert summaries into actionable tasks",
            "/feedback": "POST - Submit feedback for summaries",
            "/health": "GET - Health check for all components",
            "/stats": "GET - System statistics"
        },
        "timestamp": datetime.now().isoformat()
    }

# Health check endpoint
@app.get("/health", response_model=Dict[str, Any])
async def health_check():
    """Health check endpoint."""
    try:
        summarizer_api = get_summarizer_api()
        cognitive_api = get_cognitive_agent_api()
        
        summarizer_health = summarizer_api.health_check()
        cognitive_health = cognitive_api.health_check()
        
        overall_status = "healthy"
        if (summarizer_health.get('overall_status') != 'healthy' or 
            cognitive_health.get('overall_status') != 'healthy'):
            overall_status = "degraded"
        
        return {
            "overall_status": overall_status,
            "components": {
                "summarizer": summarizer_health,
                "cognitive_agent": cognitive_health
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {str(e)}"
        )

# Statistics endpoint
@app.get("/stats", response_model=Dict[str, Any])
async def get_system_stats():
    """Get system statistics."""
    try:
        summarizer_api = get_summarizer_api()
        cognitive_api = get_cognitive_agent_api()
        
        summarizer_stats = summarizer_api.get_performance_stats()
        cognitive_stats = cognitive_api.get_platform_statistics()
        
        return {
            "success": True,
            "summarizer_stats": summarizer_stats,
            "cognitive_agent_stats": cognitive_stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Stats retrieval failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stats retrieval failed: {str(e)}"
        )

# Metrics endpoint
@app.get("/metrics", response_model=Dict[str, Any])
async def get_metrics():
    """Lightweight JSON metrics for basic observability."""
    return {
        "success": True,
        "metrics": _metrics,
        "timestamp": datetime.now().isoformat()
    }

# Main API endpoints

@app.post("/summarize", response_model=Dict[str, Any])
async def summarize_message(message_input: MessageInput):
    """
    Process a message through SmartBrief v3 summarization with intent and urgency analysis.
    
    This endpoint:
    1. Validates the input message
    2. Stores the message in the database
    3. Processes it through SmartSummarizerV3
    4. Stores the summary results
    5. Updates user context
    """
    try:
        logger.info(f"Processing message for user {message_input.user_id} on {message_input.platform}")
        
        summarizer_api = get_summarizer_api()
        result = summarizer_api.process_message(message_input.dict())
        
        if result['success']:
            logger.info(f"Successfully processed message {result.get('message_id')} -> summary {result.get('summary_id')}")
            return result
        else:
            error_status = status.HTTP_400_BAD_REQUEST
            if result.get('error_type') == 'database_error':
                error_status = status.HTTP_503_SERVICE_UNAVAILABLE
            elif result.get('error_type') == 'internal_error':
                error_status = status.HTTP_500_INTERNAL_SERVER_ERROR
            
            raise HTTPException(
                status_code=error_status,
                detail=result['error']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in /summarize: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@app.post("/process_summary", response_model=Dict[str, Any])
async def process_summary(summary_input: SummaryInput):
    """
    Convert a summary into an actionable task using the Cognitive Agent.
    
    This endpoint:
    1. Validates the summary input
    2. Processes it through ContextFlowIntegrator
    3. Creates actionable tasks with recommendations
    4. Stores the task in the database
    5. Returns task details and recommendations
    """
    try:
        logger.info(f"Processing summary for user {summary_input.user_id} on {summary_input.platform}")
        
        cognitive_api = get_cognitive_agent_api()
        result = cognitive_api.process_summary(summary_input.dict())
        
        if result['success']:
            logger.info(f"Successfully created task {result.get('task_id')} from summary {result.get('summary_id')}")
            return result
        else:
            error_status = status.HTTP_400_BAD_REQUEST
            if result.get('error_type') == 'database_error':
                error_status = status.HTTP_503_SERVICE_UNAVAILABLE
            elif result.get('error_type') == 'internal_error':
                error_status = status.HTTP_500_INTERNAL_SERVER_ERROR
            elif result.get('error_type') == 'not_found':
                error_status = status.HTTP_404_NOT_FOUND
            
            raise HTTPException(
                status_code=error_status,
                detail=result['error']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in /process_summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@app.post("/feedback", response_model=Dict[str, Any])
async def submit_feedback(feedback_input: FeedbackInput):
    """
    Submit user feedback for a summary to improve the ML models.
    
    This endpoint:
    1. Validates the feedback input
    2. Updates the summary with feedback in the database
    3. Sends feedback to SmartSummarizerV3 for reinforcement learning
    4. Returns confirmation of feedback recording
    """
    try:
        logger.info(f"Processing feedback for summary {feedback_input.summary_id}: {feedback_input.feedback}")
        
        summarizer_api = get_summarizer_api()
        result = summarizer_api.process_feedback(feedback_input.dict())
        
        if result['success']:
            logger.info(f"Successfully recorded feedback for summary {feedback_input.summary_id}")
            return result
        else:
            error_status = status.HTTP_400_BAD_REQUEST
            if result.get('error_type') == 'database_error':
                error_status = status.HTTP_503_SERVICE_UNAVAILABLE
            elif result.get('error_type') == 'internal_error':
                error_status = status.HTTP_500_INTERNAL_SERVER_ERROR
            elif result.get('error_type') == 'not_found':
                error_status = status.HTTP_404_NOT_FOUND
            
            raise HTTPException(
                status_code=error_status,
                detail=result['error']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in /feedback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

# Additional utility endpoints

@app.get("/users/{user_id}/tasks", response_model=Dict[str, Any])
async def get_user_tasks(
    user_id: str, 
    status: Optional[str] = None,
    limit: Optional[int] = 50
):
    """Get tasks for a specific user, optionally filtered by status."""
    try:
        cognitive_api = get_cognitive_agent_api()
        result = cognitive_api.get_user_tasks(user_id, status, limit)
        
        if result['success']:
            return result
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result['error']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving tasks for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user tasks: {str(e)}"
        )

@app.put("/tasks/{task_id}/status", response_model=Dict[str, Any])
async def update_task_status(
    task_id: str,
    new_status: str,
    completion_data: Optional[Dict[str, Any]] = None
):
    """Update the status of a task."""
    try:
        cognitive_api = get_cognitive_agent_api()
        result = cognitive_api.update_task_status(task_id, new_status, completion_data)
        
        if result['success']:
            return result
        else:
            error_status = status.HTTP_400_BAD_REQUEST
            if result.get('error_type') == 'not_found':
                error_status = status.HTTP_404_NOT_FOUND
            
            raise HTTPException(
                status_code=error_status,
                detail=result['error']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update task: {str(e)}"
        )

# Full pipeline endpoint for demonstration
@app.post("/pipeline", response_model=Dict[str, Any])
async def full_pipeline(message_input: MessageInput):
    """
    Demonstrate the full pipeline: Message → Summary → Task in one call.
    This is useful for testing and demonstration purposes.
    """
    try:
        logger.info(f"Running full pipeline for user {message_input.user_id}")
        
        # Step 1: Summarize
        summarizer_api = get_summarizer_api()
        summary_result = summarizer_api.process_message(message_input.dict())
        
        if not summary_result['success']:
            return {
                'success': False,
                'error': f"Summarization failed: {summary_result['error']}",
                'step_failed': 'summarize'
            }
        
        # Step 2: Create Task (skip if auto_task already created by summarizer)
        auto_task = summary_result.get('auto_task')
        if auto_task and auto_task.get('success'):
            task_result = auto_task
        else:
            cognitive_api = get_cognitive_agent_api()
            task_result = cognitive_api.process_summary({
                'summary_id': summary_result['summary_id'],
                'user_id': message_input.user_id,
                'platform': message_input.platform,
                'summary': summary_result['summary'],
                'intent': summary_result['intent'],
                'urgency': summary_result['urgency'],
                'type': summary_result['type'],
                'confidence': summary_result['confidence'],
                'reasoning': summary_result['reasoning'],
                'context_used': summary_result['context_used'],
                'original_message': message_input.message_text
            })
        
        if not task_result['success']:
            return {
                'success': False,
                'error': f"Task creation failed: {task_result['error']}",
                'step_failed': 'process_summary',
                'summary_result': summary_result
            }
        
        # Return combined results
        return {
            'success': True,
            'message': 'Full pipeline completed successfully',
            'summary_result': summary_result,
            'task_result': task_result,
            'pipeline_summary': {
                'message_id': summary_result['message_id'],
                'summary_id': summary_result['summary_id'],
                'task_id': task_result['task_id'],
                'summary_text': summary_result['summary'],
                'task_summary': task_result['task_summary'],
                'priority': task_result['priority'],
                'recommendations_count': len(task_result.get('recommendations', []))
            },
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in full pipeline: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline execution failed: {str(e)}"
        )

# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal server error",
            "timestamp": datetime.now().isoformat()
        }
    )

# API versioned routes (/v1) mapping to the same handlers for forward compatibility
app.add_api_route("/v1/health", health_check, methods=["GET"])
app.add_api_route("/v1/stats", get_system_stats, methods=["GET"])
app.add_api_route("/v1/metrics", get_metrics, methods=["GET"])
app.add_api_route("/v1/summarize", summarize_message, methods=["POST"])
app.add_api_route("/v1/process_summary", process_summary, methods=["POST"])
app.add_api_route("/v1/feedback", submit_feedback, methods=["POST"])
app.add_api_route("/v1/users/{user_id}/tasks", get_user_tasks, methods=["GET"])
app.add_api_route("/v1/tasks/{task_id}/status", update_task_status, methods=["PUT"])
app.add_api_route("/v1/pipeline", full_pipeline, methods=["POST"])

# Main execution
if __name__ == "__main__":
    # Configuration from environment variables
    HOST = os.getenv("API_HOST", "0.0.0.0")
    PORT = int(os.getenv("API_PORT", "8000"))
    DEBUG = os.getenv("API_DEBUG", "false").lower() == "true"
    
    logger.info(f"Starting server on {HOST}:{PORT} (debug={DEBUG})")
    
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="info" if not DEBUG else "debug"
    )
