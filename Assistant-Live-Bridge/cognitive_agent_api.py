"""
Cognitive Agent API - API-compatible version of ContextFlowIntegrator for task creation.
This module provides the /process_summary endpoint functionality with database integration.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from flow_handler import ContextFlowIntegrator
from database_config import DatabaseManager

logger = logging.getLogger(__name__)

class CognitiveAgentAPI:
    """
    API wrapper for ContextFlowIntegrator with database integration.
    Handles the conversion of summaries into actionable tasks.
    """
    
    def __init__(self):
        try:
            self.integrator = ContextFlowIntegrator()
            self.db_manager = DatabaseManager()
            logger.info("CognitiveAgentAPI initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize CognitiveAgentAPI: {str(e)}")
            raise
    
    def process_summary(self, summary_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a summary and create an actionable task.
        
        Args:
            summary_data: Dictionary containing:
                - summary_id: string
                - user_id: string
                - platform: string
                - summary: string
                - intent: string
                - urgency: string
                - type: string
                - confidence: float
                - reasoning: list of strings
                - context_used: boolean
                - original_message: string (optional)
        
        Returns:
            Dictionary containing task creation results and database IDs
        """
        try:
            # Validate input
            validation_result = self._validate_summary_input(summary_data)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': validation_result['error'],
                    'error_type': 'validation_error'
                }
            
            # Convert summary data to the format expected by ContextFlowIntegrator
            platform_input = self._convert_summary_to_platform_input(summary_data)
            
            # Process through ContextFlowIntegrator
            try:
                flow_result = self.integrator.process_platform_input(platform_input)
                
                if not flow_result.get('success', False):
                    return {
                        'success': False,
                        'error': flow_result.get('error', 'Unknown processing error'),
                        'error_type': 'processing_error'
                    }
                
            except Exception as e:
                logger.error(f"ContextFlowIntegrator processing failed: {str(e)}")
                return {
                    'success': False,
                    'error': f'Task processing failed: {str(e)}',
                    'error_type': 'processing_error'
                }
            
            # Extract task data from flow result
            task_entry = flow_result['task_entry']
            recommendations = flow_result['recommendations']
            context_insights = flow_result.get('context_insights', {})
            
            # Prepare task data for database storage
            task_data = {
                'task_id': task_entry['task_id'],
                'summary_id': summary_data.get('summary_id', ''),
                'user_id': task_entry['user_id'],
                'platform': task_entry['platform'],
                'task_summary': task_entry['task_summary'],
                'task_type': task_entry['task_type'],
                'scheduled_for': task_entry.get('scheduled_for'),
                'status': task_entry['status'],
                'priority': task_entry['priority'],
                'context_score': task_entry.get('context_score', 0.0),
                'recommendations': recommendations,
                'original_message': task_entry.get('original_message', ''),
                'cognitive_metadata': {
                    'classification_confidence': summary_data.get('confidence', 0.0),
                    'scheduling_confidence': 0.8,  # Placeholder
                    'agent_version': 'CognitiveAgentAPI_v1.0',
                    'processing_timestamp': datetime.now().isoformat(),
                    'context_insights': context_insights,
                    'flow_handler_version': 'ContextFlowIntegrator'
                }
            }
            
            # Store task in database
            try:
                db_task_id = self.db_manager.store_task(task_data)
            except Exception as e:
                logger.error(f"Failed to store task: {str(e)}")
                return {
                    'success': False,
                    'error': f'Task storage failed: {str(e)}',
                    'error_type': 'database_error'
                }
            
            # Prepare response
            response = {
                'success': True,
                'task_id': task_entry['task_id'],
                'summary_id': summary_data.get('summary_id', ''),
                'task_summary': task_entry['task_summary'],
                'task_type': task_entry['task_type'],
                'scheduled_for': task_entry.get('scheduled_for'),
                'status': task_entry['status'],
                'priority': task_entry['priority'],
                'context_score': task_entry.get('context_score', 0.0),
                'recommendations': recommendations,
                'context_insights': context_insights,
                'database_ids': {
                    'task_db_id': db_task_id
                },
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"Successfully created task {task_entry['task_id']} from summary {summary_data.get('summary_id', 'unknown')}")
            return response
            
        except Exception as e:
            logger.error(f"Unexpected error in process_summary: {str(e)}")
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'error_type': 'internal_error',
                'timestamp': datetime.now().isoformat()
            }
    
    def get_user_tasks(self, user_id: str, status: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """
        Get tasks for a user, optionally filtered by status.
        
        Args:
            user_id: User identifier
            status: Optional status filter (pending, completed, etc.)
            limit: Maximum number of tasks to return
        
        Returns:
            Dictionary containing user's tasks
        """
        try:
            # Get tasks from database
            tasks = self.db_manager.get_user_tasks(user_id, status)
            
            # Limit results
            if limit and len(tasks) > limit:
                tasks = tasks[:limit]
            
            return {
                'success': True,
                'user_id': user_id,
                'status_filter': status,
                'tasks': tasks,
                'total_count': len(tasks),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error retrieving user tasks: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to retrieve user tasks: {str(e)}',
                'error_type': 'internal_error'
            }
    
    def update_task_status(self, task_id: str, new_status: str, completion_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Update the status of a task.
        
        Args:
            task_id: Task identifier
            new_status: New status (pending, in_progress, completed, cancelled, missed)
            completion_data: Optional completion metadata
        
        Returns:
            Dictionary containing update results
        """
        try:
            # Validate status
            valid_statuses = ['pending', 'in_progress', 'completed', 'cancelled', 'missed']
            if new_status not in valid_statuses:
                return {
                    'success': False,
                    'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}',
                    'error_type': 'validation_error'
                }
            
            # First attempt DB-backed status update for consistency
            try:
                db_updated = self.db_manager.update_task_status(task_id, new_status, completion_data)
                if db_updated:
                    return {
                        'success': True,
                        'task_id': task_id,
                        'new_status': new_status,
                        'updated_at': datetime.now().isoformat(),
                        'persistence': 'database'
                    }
            except Exception as e:
                logger.error(f"Database task status update failed: {str(e)}")
                # continue to fallback

            # Fallback: try to update in integrator's file-backed queue by scanning for the task
            try:
                # Find user_id owning this task in the integrator queue
                target_user = None
                for uid, tasks in getattr(self.integrator, 'task_queue', {}).items():
                    if any(t.get('task_id') == task_id for t in tasks):
                        target_user = uid
                        break
                
                if target_user:
                    updated = self.integrator.update_task_status(target_user, task_id, new_status)
                    if updated:
                        return {
                            'success': True,
                            'task_id': task_id,
                            'new_status': new_status,
                            'updated_at': datetime.now().isoformat(),
                            'persistence': 'file_queue'
                        }
                
                return {
                    'success': False,
                    'error': f'Task {task_id} not found or update failed',
                    'error_type': 'not_found'
                }

            except Exception as e:
                logger.error(f"Task status update failed: {str(e)}")
                return {
                    'success': False,
                    'error': f'Task update failed: {str(e)}',
                    'error_type': 'processing_error'
                }
            
        except Exception as e:
            logger.error(f"Unexpected error in update_task_status: {str(e)}")
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'error_type': 'internal_error'
            }
    
    def get_platform_statistics(self) -> Dict[str, Any]:
        """
        Get platform-wide statistics and insights.
        
        Returns:
            Dictionary containing platform statistics
        """
        try:
            # Get stats from integrator
            flow_stats = self.integrator.get_platform_stats()
            
            # Get database stats
            db_stats = self.db_manager.get_system_stats()
            
            return {
                'success': True,
                'platform_stats': flow_stats,
                'database_stats': db_stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error retrieving platform statistics: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to retrieve platform statistics: {str(e)}',
                'error_type': 'internal_error'
            }
    
    def _convert_summary_to_platform_input(self, summary_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert summary data to the format expected by ContextFlowIntegrator.
        
        Args:
            summary_data: Summary data from SmartSummarizer
        
        Returns:
            Dictionary in platform input format
        """
        return {
            'user_id': summary_data['user_id'],
            'platform': summary_data['platform'],
            'message_text': summary_data.get('original_message', summary_data['summary']),
            'timestamp': datetime.now().isoformat(),  # Use current time or extract from metadata
            'summary': summary_data['summary'],
            'type': summary_data.get('type', summary_data.get('intent', 'info'))
        }
    
    def _validate_summary_input(self, summary_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate input summary data.
        
        Args:
            summary_data: Input data to validate
        
        Returns:
            Dictionary with validation results
        """
        required_fields = ['user_id', 'platform', 'summary', 'intent', 'urgency']
        
        # Check required fields
        for field in required_fields:
            if field not in summary_data:
                return {
                    'valid': False,
                    'error': f'Missing required field: {field}'
                }
            
            if not summary_data[field] or (isinstance(summary_data[field], str) and not summary_data[field].strip()):
                return {
                    'valid': False,
                    'error': f'Field {field} cannot be empty'
                }
        
        # Validate platform (include teams to match API validators)
        supported_platforms = ['email', 'whatsapp', 'instagram', 'telegram', 'slack', 'teams']
        if summary_data['platform'] not in supported_platforms:
            return {
                'valid': False,
                'error': f'Platform must be one of: {", ".join(supported_platforms)}'
            }
        
        # Validate urgency
        valid_urgencies = ['low', 'medium', 'high', 'critical']
        if summary_data['urgency'] not in valid_urgencies:
            return {
                'valid': False,
                'error': f'Urgency must be one of: {", ".join(valid_urgencies)}'
            }
        
        # Validate confidence if provided
        if 'confidence' in summary_data:
            try:
                confidence = float(summary_data['confidence'])
                if not 0.0 <= confidence <= 1.0:
                    return {
                        'valid': False,
                        'error': 'Confidence must be between 0.0 and 1.0'
                    }
            except (ValueError, TypeError):
                return {
                    'valid': False,
                    'error': 'Confidence must be a valid number'
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
            
            # Check integrator
            try:
                test_input = {
                    'user_id': 'health_check',
                    'platform': 'email',
                    'message_text': 'This is a health check message.',
                    'timestamp': datetime.now().isoformat(),
                    'summary': 'Health check summary',
                    'type': 'info'
                }
                
                # Test validation without actually processing
                validation = self._validate_summary_input({
                    'user_id': 'health_check',
                    'platform': 'email',
                    'summary': 'Test',
                    'intent': 'info',
                    'urgency': 'low'
                })
                
                health_status['components']['integrator'] = 'healthy' if validation['valid'] else 'unhealthy'
            except Exception as e:
                health_status['components']['integrator'] = f'unhealthy: {str(e)}'
                health_status['overall_status'] = 'degraded'
            
            # Check database
            try:
                db_stats = self.db_manager.get_system_stats()
                health_status['components']['database'] = 'healthy' if db_stats else 'unhealthy'
            except Exception as e:
                health_status['components']['database'] = f'unhealthy: {str(e)}'
                health_status['overall_status'] = 'degraded'
            
            # Check context tracker
            try:
                context_score = self.integrator.context_tracker.get_context_score('health_check', 'info')
                health_status['components']['context_tracker'] = 'healthy'
            except Exception as e:
                health_status['components']['context_tracker'] = f'unhealthy: {str(e)}'
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
            logger.info("CognitiveAgentAPI closed successfully")
        except Exception as e:
            logger.error(f"Error closing CognitiveAgentAPI: {str(e)}")

# Singleton instance for FastAPI
_cognitive_agent_api_instance = None

def get_cognitive_agent_api() -> CognitiveAgentAPI:
    """Get singleton instance of CognitiveAgentAPI."""
    global _cognitive_agent_api_instance
    if _cognitive_agent_api_instance is None:
        _cognitive_agent_api_instance = CognitiveAgentAPI()
    return _cognitive_agent_api_instance

def close_cognitive_agent_api():
    """Close the singleton instance."""
    global _cognitive_agent_api_instance
    if _cognitive_agent_api_instance is not None:
        _cognitive_agent_api_instance.close()
        _cognitive_agent_api_instance = None