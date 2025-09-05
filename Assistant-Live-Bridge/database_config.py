"""
Database Configuration and Connection Utilities
Supports both MongoDB and PostgreSQL for the integrated system.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# MongoDB imports
try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    logging.warning("PyMongo not available. MongoDB support disabled.")

# PostgreSQL imports
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    import psycopg2.pool
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logging.warning("psycopg2 not available. PostgreSQL support disabled.")

# Environment variables
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'smartbrief_cognitive_agent')

POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'smartbrief_cognitive_agent')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password')

DATABASE_TYPE = os.getenv('DATABASE_TYPE', 'mongodb')  # 'mongodb' or 'postgresql'

class DatabaseManager:
    """
    Unified database manager supporting both MongoDB and PostgreSQL, with demo mode.
    """
    
    def __init__(self, db_type: str = None):
        self.db_type = db_type or DATABASE_TYPE
        self.connection = None
        self.database = None
        self.demo_mode = self.db_type == 'demo'
        
        if self.demo_mode:
            self._setup_demo_mode()
        elif self.db_type == 'mongodb' and MONGODB_AVAILABLE:
            self._setup_mongodb()
        elif self.db_type == 'postgresql' and POSTGRES_AVAILABLE:
            self._setup_postgresql()
        else:
            logging.warning(f"Database type '{self.db_type}' not supported or dependencies missing. Running in demo mode.")
            self.demo_mode = True
            self._setup_demo_mode()
    
    def _setup_demo_mode(self):
        """Initialize demo mode with in-memory storage."""
        self.demo_storage = {
            'messages': [],
            'summaries': [],
            'tasks': []
        }
        logging.info("Database manager initialized in demo mode (in-memory storage)")
    
    def _setup_mongodb(self):
        """Initialize MongoDB connection."""
        try:
            self.connection = MongoClient(
                MONGODB_URI,
                serverSelectionTimeoutMS=5000,
                maxPoolSize=50,
                minPoolSize=5
            )
            
            # Test connection
            self.connection.admin.command('ping')
            self.database = self.connection[MONGODB_DATABASE]
            
            # Create indexes
            self._create_mongodb_indexes()
            
            logging.info("MongoDB connection established successfully")
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logging.error(f"Failed to connect to MongoDB: {str(e)}")
            raise
    
    def _setup_postgresql(self):
        """Initialize PostgreSQL connection."""
        try:
            connection_string = f"host='{POSTGRES_HOST}' port='{POSTGRES_PORT}' dbname='{POSTGRES_DB}' user='{POSTGRES_USER}' password='{POSTGRES_PASSWORD}'"
            
            # Create connection pool
            self.connection = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=20,
                dsn=connection_string
            )
            
            # Test connection
            test_conn = self.connection.getconn()
            test_conn.close()
            self.connection.putconn(test_conn)
            
            # Create tables
            self._create_postgresql_tables()
            
            logging.info("PostgreSQL connection established successfully")
            
        except Exception as e:
            logging.error(f"Failed to connect to PostgreSQL: {str(e)}")
            raise
    
    def _create_mongodb_indexes(self):
        """Create MongoDB indexes for optimal performance."""
        try:
            # Messages collection indexes
            messages = self.database.messages
            messages.create_index("user_id")
            messages.create_index("platform")
            messages.create_index([("timestamp", -1)])
            messages.create_index("message_id", unique=True)
            
            # Summaries collection indexes
            summaries = self.database.summaries
            summaries.create_index("summary_id", unique=True)
            summaries.create_index("message_id")
            summaries.create_index("user_id")
            summaries.create_index("urgency")
            summaries.create_index("intent")
            summaries.create_index([("created_at", -1)])
            
            # Tasks collection indexes
            tasks = self.database.tasks
            tasks.create_index("task_id", unique=True)
            tasks.create_index("summary_id")
            tasks.create_index("user_id")
            tasks.create_index("status")
            tasks.create_index("priority")
            tasks.create_index("scheduled_for")
            tasks.create_index([("created_at", -1)])
            
            logging.info("MongoDB indexes created successfully")
            
        except Exception as e:
            logging.error(f"Error creating MongoDB indexes: {str(e)}")
    
    def _create_postgresql_tables(self):
        """Create PostgreSQL tables."""
        try:
            conn = self.connection.getconn()
            cursor = conn.cursor()
            
            # Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    platform VARCHAR(50) NOT NULL,
                    message_text TEXT NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                    message_id VARCHAR(255) UNIQUE NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # Summaries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS summaries (
                    id SERIAL PRIMARY KEY,
                    summary_id VARCHAR(255) UNIQUE NOT NULL,
                    message_id VARCHAR(255) NOT NULL,
                    user_id VARCHAR(255) NOT NULL,
                    platform VARCHAR(50) NOT NULL,
                    summary TEXT NOT NULL,
                    intent VARCHAR(100),
                    urgency VARCHAR(50),
                    type VARCHAR(100),
                    confidence FLOAT,
                    reasoning JSONB,
                    context_used BOOLEAN DEFAULT FALSE,
                    feedback JSONB,
                    processing_metadata JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    FOREIGN KEY (message_id) REFERENCES messages(message_id)
                );
            """)
            
            # Tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    task_id VARCHAR(255) UNIQUE NOT NULL,
                    summary_id VARCHAR(255) NOT NULL,
                    user_id VARCHAR(255) NOT NULL,
                    platform VARCHAR(50) NOT NULL,
                    task_summary TEXT NOT NULL,
                    task_type VARCHAR(100),
                    scheduled_for TIMESTAMP WITH TIME ZONE,
                    status VARCHAR(50) DEFAULT 'pending',
                    priority VARCHAR(50),
                    context_score FLOAT,
                    recommendations JSONB,
                    original_message TEXT,
                    cognitive_metadata JSONB,
                    completion_data JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    FOREIGN KEY (summary_id) REFERENCES summaries(summary_id)
                );
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_platform ON messages(platform);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp DESC);")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_summaries_user_id ON summaries(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_summaries_urgency ON summaries(urgency);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_summaries_intent ON summaries(intent);")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_scheduled_for ON tasks(scheduled_for);")
            
            conn.commit()
            cursor.close()
            self.connection.putconn(conn)
            
            logging.info("PostgreSQL tables and indexes created successfully")
            
        except Exception as e:
            logging.error(f"Error creating PostgreSQL tables: {str(e)}")
            if conn:
                conn.rollback()
                cursor.close()
                self.connection.putconn(conn)
            raise
    
    # Messages operations
    def store_message(self, message_data: Dict[str, Any]) -> str:
        """Store a message in the database."""
        try:
            if self.demo_mode:
                return self._store_message_demo(message_data)
            elif self.db_type == 'mongodb':
                return self._store_message_mongodb(message_data)
            else:
                return self._store_message_postgresql(message_data)
        except Exception as e:
            logging.error(f"Error storing message: {str(e)}")
            raise
    
    def _store_message_demo(self, message_data: Dict[str, Any]) -> str:
        """Store message in demo mode (in-memory)."""
        message_data['id'] = len(self.demo_storage['messages']) + 1
        message_data['created_at'] = datetime.now()
        message_data['updated_at'] = datetime.now()
        self.demo_storage['messages'].append(message_data)
        return str(message_data['id'])
    
    def _store_message_mongodb(self, message_data: Dict[str, Any]) -> str:
        """Store message in MongoDB."""
        message_data['created_at'] = datetime.now()
        message_data['updated_at'] = datetime.now()
        
        result = self.database.messages.insert_one(message_data)
        return str(result.inserted_id)
    
    def _store_message_postgresql(self, message_data: Dict[str, Any]) -> str:
        """Store message in PostgreSQL."""
        conn = self.connection.getconn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO messages (user_id, platform, message_text, timestamp, message_id, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (
                message_data['user_id'],
                message_data['platform'],
                message_data['message_text'],
                message_data['timestamp'],
                message_data['message_id'],
                json.dumps(message_data.get('metadata', {}))
            ))
            
            message_id = cursor.fetchone()[0]
            conn.commit()
            return str(message_id)
            
        finally:
            cursor.close()
            self.connection.putconn(conn)
    
    # Summaries operations
    def store_summary(self, summary_data: Dict[str, Any]) -> str:
        """Store a summary in the database."""
        try:
            if self.demo_mode:
                return self._store_summary_demo(summary_data)
            elif self.db_type == 'mongodb':
                return self._store_summary_mongodb(summary_data)
            else:
                return self._store_summary_postgresql(summary_data)
        except Exception as e:
            logging.error(f"Error storing summary: {str(e)}")
            raise
    
    def _store_summary_demo(self, summary_data: Dict[str, Any]) -> str:
        """Store summary in demo mode (in-memory)."""
        summary_data['id'] = len(self.demo_storage['summaries']) + 1
        summary_data['created_at'] = datetime.now()
        summary_data['updated_at'] = datetime.now()
        self.demo_storage['summaries'].append(summary_data)
        return str(summary_data['id'])
    
    def _store_summary_mongodb(self, summary_data: Dict[str, Any]) -> str:
        """Store summary in MongoDB."""
        summary_data['created_at'] = datetime.now()
        summary_data['updated_at'] = datetime.now()
        
        result = self.database.summaries.insert_one(summary_data)
        return str(result.inserted_id)
    
    def _store_summary_postgresql(self, summary_data: Dict[str, Any]) -> str:
        """Store summary in PostgreSQL."""
        conn = self.connection.getconn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO summaries (
                    summary_id, message_id, user_id, platform, summary, intent,
                    urgency, type, confidence, reasoning, context_used, 
                    processing_metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (
                summary_data['summary_id'],
                summary_data['message_id'],
                summary_data['user_id'],
                summary_data['platform'],
                summary_data['summary'],
                summary_data['intent'],
                summary_data['urgency'],
                summary_data['type'],
                summary_data['confidence'],
                json.dumps(summary_data.get('reasoning', [])),
                summary_data.get('context_used', False),
                json.dumps(summary_data.get('processing_metadata', {}))
            ))
            
            summary_id = cursor.fetchone()[0]
            conn.commit()
            return str(summary_id)
            
        finally:
            cursor.close()
            self.connection.putconn(conn)
    
    # Tasks operations
    def store_task(self, task_data: Dict[str, Any]) -> str:
        """Store a task in the database."""
        try:
            if self.demo_mode:
                return self._store_task_demo(task_data)
            elif self.db_type == 'mongodb':
                return self._store_task_mongodb(task_data)
            else:
                return self._store_task_postgresql(task_data)
        except Exception as e:
            logging.error(f"Error storing task: {str(e)}")
            raise
    
    def _store_task_demo(self, task_data: Dict[str, Any]) -> str:
        """Store task in demo mode (in-memory)."""
        task_data['id'] = len(self.demo_storage['tasks']) + 1
        task_data['created_at'] = datetime.now()
        task_data['updated_at'] = datetime.now()
        self.demo_storage['tasks'].append(task_data)
        return str(task_data['id'])
    
    def _store_task_mongodb(self, task_data: Dict[str, Any]) -> str:
        """Store task in MongoDB."""
        task_data['created_at'] = datetime.now()
        task_data['updated_at'] = datetime.now()
        
        result = self.database.tasks.insert_one(task_data)
        return str(result.inserted_id)
    
    def _store_task_postgresql(self, task_data: Dict[str, Any]) -> str:
        """Store task in PostgreSQL."""
        conn = self.connection.getconn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO tasks (
                    task_id, summary_id, user_id, platform, task_summary, task_type,
                    scheduled_for, status, priority, context_score, recommendations,
                    original_message, cognitive_metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (
                task_data['task_id'],
                task_data['summary_id'],
                task_data['user_id'],
                task_data['platform'],
                task_data['task_summary'],
                task_data['task_type'],
                task_data.get('scheduled_for'),
                task_data.get('status', 'pending'),
                task_data.get('priority'),
                task_data.get('context_score'),
                json.dumps(task_data.get('recommendations', [])),
                task_data.get('original_message'),
                json.dumps(task_data.get('cognitive_metadata', {}))
            ))
            
            task_id = cursor.fetchone()[0]
            conn.commit()
            return str(task_id)
            
        finally:
            cursor.close()
            self.connection.putconn(conn)
    
    def update_task_status(self, task_id: str, new_status: str, completion_data: Optional[Dict[str, Any]] = None) -> bool:
        """Update a task's status across supported backends.
        Returns True if a record was updated, False otherwise.
        """
        try:
            if self.demo_mode:
                for t in getattr(self, 'demo_storage', {}).get('tasks', []):
                    if t.get('task_id') == task_id:
                        t['status'] = new_status
                        if completion_data is not None:
                            t['completion_data'] = completion_data
                        t['updated_at'] = datetime.now()
                        return True
                return False
            elif self.db_type == 'mongodb':
                result = self.database.tasks.update_one(
                    {'task_id': task_id},
                    {'$set': {
                        'status': new_status,
                        'completion_data': completion_data,
                        'updated_at': datetime.now()
                    }}
                )
                return result.modified_count > 0
            else:
                conn = self.connection.getconn()
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        """
                        UPDATE tasks 
                        SET status = %s, completion_data = %s, updated_at = NOW()
                        WHERE task_id = %s;
                        """,
                        (new_status, json.dumps(completion_data) if completion_data is not None else None, task_id)
                    )
                    conn.commit()
                    return cursor.rowcount > 0
                finally:
                    cursor.close()
                    self.connection.putconn(conn)
        except Exception as e:
            logging.error(f"Error updating task status: {str(e)}")
            return False

    # Feedback operations
    def update_summary_feedback(self, summary_id: str, feedback: str, comment: str = "") -> bool:
        """Update summary with user feedback."""
        try:
            feedback_data = {
                'rating': feedback,
                'comment': comment,
                'feedback_timestamp': datetime.now()
            }
            
            if self.demo_mode:
                # Find and update summary in demo storage
                for summary in self.demo_storage['summaries']:
                    if summary.get('summary_id') == summary_id:
                        summary['feedback'] = feedback_data
                        summary['updated_at'] = datetime.now()
                        return True
                return False
            elif self.db_type == 'mongodb':
                result = self.database.summaries.update_one(
                    {'summary_id': summary_id},
                    {
                        '$set': {
                            'feedback': feedback_data,
                            'updated_at': datetime.now()
                        }
                    }
                )
                return result.modified_count > 0
            else:
                conn = self.connection.getconn()
                cursor = conn.cursor()
                try:
                    cursor.execute("""
                        UPDATE summaries 
                        SET feedback = %s, updated_at = NOW()
                        WHERE summary_id = %s;
                    """, (json.dumps(feedback_data), summary_id))
                    
                    conn.commit()
                    return cursor.rowcount > 0
                finally:
                    cursor.close()
                    self.connection.putconn(conn)
                    
        except Exception as e:
            logging.error(f"Error updating feedback: {str(e)}")
            return False
    
    # Query operations
    def get_user_messages(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get messages for a user."""
        try:
            if self.db_type == 'mongodb':
                cursor = self.database.messages.find(
                    {'user_id': user_id}
                ).sort('timestamp', -1).limit(limit)
                return list(cursor)
            else:
                conn = self.connection.getconn()
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                try:
                    cursor.execute("""
                        SELECT * FROM messages 
                        WHERE user_id = %s 
                        ORDER BY timestamp DESC 
                        LIMIT %s;
                    """, (user_id, limit))
                    
                    return [dict(row) for row in cursor.fetchall()]
                finally:
                    cursor.close()
                    self.connection.putconn(conn)
                    
        except Exception as e:
            logging.error(f"Error getting user messages: {str(e)}")
            return []
    
    def get_user_tasks(self, user_id: str, status: str = None) -> List[Dict[str, Any]]:
        """Get tasks for a user, optionally filtered by status."""
        try:
            if self.demo_mode:
                tasks = [t for t in self.demo_storage.get('tasks', []) if t.get('user_id') == user_id]
                if status:
                    tasks = [t for t in tasks if t.get('status') == status]
                return tasks
            if self.db_type == 'mongodb':
                query = {'user_id': user_id}
                if status:
                    query['status'] = status
                    
                cursor = self.database.tasks.find(query).sort('created_at', -1)
                return list(cursor)
            else:
                conn = self.connection.getconn()
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                try:
                    if status:
                        cursor.execute("""
                            SELECT * FROM tasks 
                            WHERE user_id = %s AND status = %s 
                            ORDER BY created_at DESC;
                        """, (user_id, status))
                    else:
                        cursor.execute("""
                            SELECT * FROM tasks 
                            WHERE user_id = %s 
                            ORDER BY created_at DESC;
                        """, (user_id,))
                    
                    return [dict(row) for row in cursor.fetchall()]
                finally:
                    cursor.close()
                    self.connection.putconn(conn)
                    
        except Exception as e:
            logging.error(f"Error getting user tasks: {str(e)}")
            return []
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get system-wide statistics."""
        try:
            if self.demo_mode:
                return {
                    'total_messages': len(self.demo_storage['messages']),
                    'total_summaries': len(self.demo_storage['summaries']),
                    'total_tasks': len(self.demo_storage['tasks']),
                    'pending_tasks': len([t for t in self.demo_storage['tasks'] if t.get('status') == 'pending']),
                    'completed_tasks': len([t for t in self.demo_storage['tasks'] if t.get('status') == 'completed'])
                }
            elif self.db_type == 'mongodb':
                return {
                    'total_messages': self.database.messages.count_documents({}),
                    'total_summaries': self.database.summaries.count_documents({}),
                    'total_tasks': self.database.tasks.count_documents({}),
                    'pending_tasks': self.database.tasks.count_documents({'status': 'pending'}),
                    'completed_tasks': self.database.tasks.count_documents({'status': 'completed'})
                }
            else:
                conn = self.connection.getconn()
                cursor = conn.cursor()
                try:
                    cursor.execute("""
                        SELECT 
                            (SELECT COUNT(*) FROM messages) as total_messages,
                            (SELECT COUNT(*) FROM summaries) as total_summaries,
                            (SELECT COUNT(*) FROM tasks) as total_tasks,
                            (SELECT COUNT(*) FROM tasks WHERE status = 'pending') as pending_tasks,
                            (SELECT COUNT(*) FROM tasks WHERE status = 'completed') as completed_tasks;
                    """)
                    
                    row = cursor.fetchone()
                    return {
                        'total_messages': row[0],
                        'total_summaries': row[1],
                        'total_tasks': row[2],
                        'pending_tasks': row[3],
                        'completed_tasks': row[4]
                    }
                finally:
                    cursor.close()
                    self.connection.putconn(conn)
                    
        except Exception as e:
            logging.error(f"Error getting system stats: {str(e)}")
            return {}
    
    def close(self):
        """Close database connection."""
        try:
            if self.connection:
                if self.db_type == 'mongodb':
                    self.connection.close()
                else:
                    self.connection.closeall()
                logging.info("Database connection closed")
        except Exception as e:
            logging.error(f"Error closing database connection: {str(e)}")

# Utility functions
def get_database_manager() -> DatabaseManager:
    """Get a database manager instance."""
    return DatabaseManager()

def test_database_connection() -> bool:
    """Test database connection."""
    try:
        db = DatabaseManager()
        if db.demo_mode:
            logging.info("Database test: Running in demo mode")
            return True
        stats = db.get_system_stats()
        db.close()
        return True
    except Exception as e:
        logging.error(f"Database connection test failed: {str(e)}")
        return False