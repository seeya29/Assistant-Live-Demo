"""
Smart Summarizer API - API-compatible version of SmartSummarizerV3 with database integration.
This module provides the /summarize endpoint functionality with database storage,
auto-enqueue into the cognitive agent queue, and feedback-driven learning integration.
"""

import uuid
import logging
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
from smart_summarizer_v3 import SmartSummarizerV3
from context_loader import ContextLoader
from database_config import DatabaseManager
from cognitive_agent_api import get_cognitive_agent_api

logger = logging.getLogger(__name__)

class SmartSummarizerAPI:
    """
    API wrapper for SmartSummarizerV3 with database integration and queue wiring.
    - Stores messages and summaries in the configured DB (or demo store)
    - Optionally enqueues a task directly into Sankalp's queue after summarization
    - Integrates feedback with a persistent learning trace
    """
    
    def __init__(self):
        try:
            self.context_loader = ContextLoader()
            self.summarizer = SmartSummarizerV3()  # Enhanced version handles context internally
            self.db_manager = DatabaseManager()
            self.auto_enqueue = os.getenv("AUTO_ENQUEUE_TASK", "true").lower() == "true"
            # summary_id -> summary text index for feedback learning
            self.feedback_index_path = os.path.join(os.getcwd(), 'summary_index.json')
            self.summary_index = self._load_summary_index()
            logger.info("SmartSummarizerAPI initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize SmartSummarizerAPI: {str(e)}")
            raise

    def _load_summary_index(self) -> Dict[str, str]:
        try:
            if os.path.exists(self.feedback_index_path):
                with open(self.feedback_index_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load summary index: {e}")
        return {}

    def _save_summary_index(self):
        try:
            with open(self.feedback_index_path, 'w', encoding='utf-8') as f:
                json.dump(self.summary_index, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save summary index: {e}")
    
    def process_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a message through the full summarization pipeline with database storage.
        Optionally auto-enqueue a task into the cognitive agent queue.
        
        Args:
            message_data: Dictionary containing:
                - user_id: string
                - platform: string (free-form; previously restricted set)
                - message_text: string
                - timestamp: ISO 8601 datetime string
                - message_id: string (optional, will generate if not provided)
                - metadata: dict (optional)
        
        Returns:
            Dictionary containing summary results, database IDs, and optional auto-task details
        """
        try:
            # Validate input
            validation_result = self._validate_input(message_data)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': validation_result['error'],
                    'error_type': 'validation_error'
                }
            
            # Generate message ID if not provided
            if 'message_id' not in message_data or not message_data['message_id']:
                message_data['message_id'] = f"msg_{uuid.uuid4().hex[:12]}"
            
            # Store message in database
            try:
                db_message_id = self.db_manager.store_message(message_data)
            except Exception as e:
                logger.error(f"Failed to store message: {str(e)}")
                return {
                    'success': False,
                    'error': f'Database storage failed: {str(e)}',
                    'error_type': 'database_error'
                }
            
            # Generate summary using SmartSummarizerV3
            try:
                summary_result = self.summarizer.summarize(message_data, use_context=True)
            except Exception as e:
                logger.error(f"Summarization failed: {str(e)}")
                return {
                    'success': False,
                    'error': f'Summarization failed: {str(e)}',
                    'error_type': 'summarization_error'
                }
            
            # Prepare summary data for database storage
            summary_id = f"sum_{uuid.uuid4().hex[:12]}"
            summary_data = {
                'summary_id': summary_id,
                'message_id': message_data['message_id'],
                'user_id': message_data['user_id'],
                'platform': message_data['platform'],
                'summary': summary_result['summary'],
                'intent': summary_result['intent'],
                'urgency': summary_result['urgency'],
                'type': summary_result['type'],
                'confidence': summary_result['confidence'],
                'reasoning': summary_result['reasoning'],
                'context_used': summary_result['context_used'],
                'processing_metadata': summary_result['metadata']
            }
            
            # Store summary in database
            try:
                db_summary_id = self.db_manager.store_summary(summary_data)
            except Exception as e:
                logger.error(f"Failed to store summary: {str(e)}")
                return {
                    'success': False,
                    'error': f'Summary storage failed: {str(e)}',
                    'error_type': 'database_error'
                }
            
            # Update context with new message and summary
            try:
                self.context_loader.update_context(
                    user_id=message_data['user_id'],
                    platform=message_data['platform'],
                    message_data=message_data,
                    summary_data=summary_result
                )
            except Exception as e:
                logger.warning(f"Context update failed: {str(e)}")
                # Non-fatal

            # Persist mapping for feedback learning
            try:
                self.summary_index[summary_id] = summary_result['summary']
                self._save_summary_index()
            except Exception as e:
                logger.warning(f"Failed to update summary index: {e}")

            response = {
                'success': True,
                'summary_id': summary_id,
                'message_id': message_data['message_id'],
                'summary': summary_result['summary'],
                'intent': summary_result['intent'],
                'urgency': summary_result['urgency'],
                'type': summary_result['type'],
                'confidence': summary_result['confidence'],
                'reasoning': summary_result['reasoning'],
                'context_used': summary_result['context_used'],
                'processing_metadata': summary_result['metadata'],
                'database_ids': {
                    'message_db_id': db_message_id,
                    'summary_db_id': db_summary_id
                },
                'timestamp': datetime.now().isoformat()
            }

            # Optional: auto-enqueue a task using the cognitive agent
            if self.auto_enqueue:
                try:
                    cognitive_api = get_cognitive_agent_api()
                    task_payload = {
                        'summary_id': summary_id,
                        'user_id': message_data['user_id'],
                        'platform': message_data['platform'],
                        'summary': summary_result['summary'],
                        'intent': summary_result['intent'],
                        'urgency': summary_result['urgency'],
                        'type': summary_result['type'],
                        'confidence': summary_result['confidence'],
                        'reasoning': summary_result['reasoning'],
                        'context_used': summary_result['context_used'],
                        'original_message': message_data['message_text']
                    }
                    task_result = cognitive_api.process_summary(task_payload)
                    response['auto_task'] = task_result
                except Exception as e:
                    logger.warning(f"Auto-enqueue task failed: {e}")
                    response['auto_task'] = {
                        'success': False,
                        'error': f'Auto-enqueue failed: {str(e)}'
                    }

            logger.info(f"Successfully processed message {message_data['message_id']} for user {message_data['user_id']}")
            return response
            
        except Exception as e:
            logger.error(f"Unexpected error in process_message: {str(e)}")
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'error_type': 'internal_error',
                'timestamp': datetime.now().isoformat()
            }
    
    def process_feedback(self, feedback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process user feedback for a summary and update learning trace.
        
        Args:
            feedback_data: Dictionary containing:
                - summary_id: string
                - feedback: string ('upvote' or 'downvote')
                - comment: string (optional)
        
        Returns:
            Dictionary containing feedback processing results
        """
        try:
            # Validate feedback input
            required_fields = ['summary_id', 'feedback']
            for field in required_fields:
                if field not in feedback_data:
                    return {
                        'success': False,
                        'error': f'Missing required field: {field}',
                        'error_type': 'validation_error'
                    }
            
            summary_id = feedback_data['summary_id']
            feedback = feedback_data['feedback']
            comment = feedback_data.get('comment', '')
            
            # Validate feedback value
            if feedback not in ['upvote', 'downvote']:
                return {
                    'success': False,
                    'error': 'Feedback must be either "upvote" or "downvote"',
                    'error_type': 'validation_error'
                }
            
            # Update database with feedback
            try:
                updated = self.db_manager.update_summary_feedback(summary_id, feedback, comment)
                if not updated:
                    return {
                        'success': False,
                        'error': f'Summary with ID {summary_id} not found',
                        'error_type': 'not_found'
                    }
            except Exception as e:
                logger.error(f"Failed to update feedback in database: {str(e)}")
                return {
                    'success': False,
                    'error': f'Database update failed: {str(e)}',
                    'error_type': 'database_error'
                }
            
            # Retrieve summary text from the index for learning
            summary_text = self.summary_index.get(summary_id, '')
            
            # Update summarizer's learning system
            try:
                self.summarizer.receive_feedback(summary_id, feedback, comment, summary_text=summary_text)
            except Exception as e:
                logger.warning(f"Summarizer feedback update failed: {str(e)}")
                # Non-fatal
            
            logger.info(f"Processed feedback for summary {summary_id}: {feedback}")
            return {
                'success': True,
                'message': 'Feedback recorded successfully',
                'summary_id': summary_id,
                'feedback': feedback,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Unexpected error in process_feedback: {str(e)}")
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'error_type': 'internal_error',
                'timestamp': datetime.now().isoformat()
            }
    
    def get_user_summary_history(self, user_id: str, limit: int = 50) -> Dict[str, Any]:
        """
        Get summary history for a user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of summaries to return
        
        Returns:
            Dictionary containing user's summary history
        """
        try:
            # This would require implementing a method in DatabaseManager
            # For now, return a placeholder response
            return {
                'success': True,
                'user_id': user_id,
                'summaries': [],  # Would be populated from database
                'total_count': 0,
                'message': 'Summary history retrieval not yet implemented'
            }
            
        except Exception as e:
            logger.error(f"Error retrieving summary history: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to retrieve summary history: {str(e)}',
                'error_type': 'internal_error'
            }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get summarizer performance statistics.
        
        Returns:
            Dictionary containing performance metrics
        """
        try:
            # Get stats from summarizer
            summarizer_stats = self.summarizer.get_performance_stats()
            
            # Get database stats
            db_stats = self.db_manager.get_system_stats()
            
            return {
                'success': True,
                'summarizer_performance': summarizer_stats,
                'database_stats': db_stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error retrieving performance stats: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to retrieve performance stats: {str(e)}',
                'error_type': 'internal_error'
            }
    
    def _validate_input(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate input message data. Platform is free-form (no hardcoded enumerations).
        
        Args:
            message_data: Input data to validate
        
        Returns:
            Dictionary with validation results
        """
        required_fields = ['user_id', 'platform', 'message_text', 'timestamp']
        
        # Check required fields
        for field in required_fields:
            if field not in message_data:
                return {
                    'valid': False,
                    'error': f'Missing required field: {field}'
                }
            
            if not message_data[field] or (isinstance(message_data[field], str) and not message_data[field].strip()):
                return {
                    'valid': False,
                    'error': f'Field {field} cannot be empty'
                }
        
        # Accept any non-empty platform string; normalize to lowercase
        message_data['platform'] = str(message_data['platform']).strip().lower()
        
        # Validate timestamp format
        try:
            datetime.fromisoformat(message_data['timestamp'].replace('Z', '+00:00'))
        except ValueError:
            return {
                'valid': False,
                'error': 'Invalid timestamp format. Use ISO 8601 format.'
            }
        
        # Validate message text length
        if len(message_data['message_text']) > 10000:
            return {
                'valid': False,
                'error': 'Message text too long (max 10,000 characters)'
            }
        
        return {'valid': True}
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all components.
        
        Returns:
            Dictionary containing health status
        """
        try:
            health_status = {
                'overall_status': 'healthy',
                'components': {},
                'timestamp': datetime.now().isoformat()
            }
            
            # Check summarizer
            try:
                test_message = {
                    'user_id': 'health_check',
                    'platform': 'email',
                    'message_text': 'This is a health check message.',
                    'timestamp': datetime.now().isoformat()
                }
                # Validate a dummy input
                validation = self._validate_input(test_message)
                health_status['components']['summarizer'] = 'healthy' if validation['valid'] else 'unhealthy'
            except Exception as e:
                health_status['components']['summarizer'] = f'unhealthy: {str(e)}'
                health_status['overall_status'] = 'degraded'
            
            # Check database
            try:
                db_stats = self.db_manager.get_system_stats()
                health_status['components']['database'] = 'healthy' if db_stats is not None else 'unhealthy'
            except Exception as e:
                health_status['components']['database'] = f'unhealthy: {str(e)}'
                health_status['overall_status'] = 'degraded'
            
            # Check context loader
            try:
                _ = self.context_loader.get_user_context_summary('health_check')
                health_status['components']['context_loader'] = 'healthy'
            except Exception as e:
                health_status['components']['context_loader'] = f'unhealthy: {str(e)}'
                health_status['overall_status'] = 'degraded'
            
            return health_status
            
        except Exception as e:
            return {
                'overall_status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def close(self):
        """Close all connections and clean up resources."""
        try:
            if hasattr(self, 'db_manager'):
                self.db_manager.close()
            if hasattr(self, 'context_loader'):
                self.context_loader.save_user_patterns()
            logger.info("SmartSummarizerAPI closed successfully")
        except Exception as e:
            logger.error(f"Error closing SmartSummarizerAPI: {str(e)}")

# Singleton instance for FastAPI
_summarizer_api_instance = None

def get_summarizer_api() -> SmartSummarizerAPI:
    """Get singleton instance of SmartSummarizerAPI."""
    global _summarizer_api_instance
    if _summarizer_api_instance is None:
        _summarizer_api_instance = SmartSummarizerAPI()
    return _summarizer_api_instance

def close_summarizer_api():
    """Close the singleton instance."""
    global _summarizer_api_instance
    if _summarizer_api_instance is not None:
        _summarizer_api_instance.close()
        _summarizer_api_instance = None
