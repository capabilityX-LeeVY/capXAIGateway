"""
Session Info Manager
Manages session information recording to database.
"""

import json
import time
from typing import Optional, Dict, Any
from datetime import datetime
from db.db_connection_manager import get_db_connection
from common.utils.logger import LOGGER_ERROR, LOGGER_DEBUG


class SessionInfoManager:
    """
    Session Information Manager
    Handles recording of session access requests to the database.
    """
    
    def __init__(self, db_name: str = 'capx_ai_gateway_db'):
        """
        Initialize SessionInfoManager.
        
        Args:
            db_name (str): Database name to use for session recording
        """
        self.db_name = db_name
    
    def record_session_request(self, 
                             session_id: str,
                             user_id: Optional[str] = None,
                             user_ip: Optional[str] = None,
                             user_agent: Optional[str] = None,
                             request_method: str = 'GET',
                             request_path: str = '/',
                             request_params: Optional[Dict] = None,
                             request_headers: Optional[Dict] = None,
                             response_status: Optional[int] = None,
                             response_time_ms: Optional[int] = None,
                             request_size: Optional[int] = None,
                             response_size: Optional[int] = None,
                             error_message: Optional[str] = None,
                             session_start_time: Optional[datetime] = None,
                             session_end_time: Optional[datetime] = None,
                             is_active: bool = True,
                             # New file-related parameters
                             uploaded_file_name: Optional[str] = None,
                             stored_file_path: Optional[str] = None,
                             file_size: Optional[int] = None,
                             file_type: Optional[str] = None,
                             file_hash: Optional[str] = None) -> bool:
        """
        Record a session request to the database.
        
        Args:
            session_id (str): Session ID
            user_id (Optional[str]): User ID
            user_ip (Optional[str]): User IP address
            user_agent (Optional[str]): User agent string
            request_method (str): HTTP request method
            request_path (str): Request path
            request_params (Optional[Dict]): Request parameters
            request_headers (Optional[Dict]): Request headers
            response_status (Optional[int]): HTTP response status code
            response_time_ms (Optional[int]): Response time in milliseconds
            request_size (Optional[int]): Request size in bytes
            response_size (Optional[int]): Response size in bytes
            error_message (Optional[str]): Error message if any
            session_start_time (Optional[datetime]): Session start time
            session_end_time (Optional[datetime]): Session end time
            is_active (bool): Whether session is active
            uploaded_file_name (Optional[str]): Original uploaded file name
            stored_file_path (Optional[str]): Stored file path on server
            file_size (Optional[int]): File size in bytes
            file_type (Optional[str]): File MIME type
            file_hash (Optional[str]): File SHA-256 hash
        
        Returns:
            bool: True if successful, False otherwise
        """
        connection = None
        try:
            connection = get_db_connection(self.db_name)
            if not connection:
                LOGGER_ERROR(f"Failed to get database connection for {self.db_name}")
                return False
            
            with connection.cursor() as cursor:
                # Prepare data
                request_params_json = json.dumps(request_params, ensure_ascii=False) if request_params else None
                request_headers_json = json.dumps(request_headers, ensure_ascii=False) if request_headers else None
                
                # Insert query with file fields
                insert_sql = """
                INSERT INTO session_info (
                    session_id, user_id, user_ip, user_agent, request_method, 
                    request_path, request_params, request_headers, response_status,
                    response_time_ms, request_size, response_size, error_message,
                    session_start_time, session_end_time, is_active,
                    uploaded_file_name, stored_file_path, file_size, file_type, file_hash
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                """
                
                values = (
                    session_id, user_id, user_ip, user_agent, request_method,
                    request_path, request_params_json, request_headers_json, response_status,
                    response_time_ms, request_size, response_size, error_message,
                    session_start_time, session_end_time, is_active,
                    uploaded_file_name, stored_file_path, file_size, file_type, file_hash
                )
                
                cursor.execute(insert_sql, values)
                connection.commit()
                
                LOGGER_DEBUG(f"Successfully recorded session request for session_id: {session_id}")
                return True
                
        except Exception as e:
            LOGGER_ERROR(f"Failed to record session request: {str(e)}")
            if connection:
                connection.rollback()
            return False
            
        finally:
            if connection:
                connection.close()
    
    def get_session_requests(self, 
                           session_id: Optional[str] = None,
                           user_id: Optional[str] = None,
                           start_time: Optional[datetime] = None,
                           end_time: Optional[datetime] = None,
                           limit: int = 100) -> list:
        """
        Retrieve session requests from database.
        
        Args:
            session_id (Optional[str]): Filter by session ID
            user_id (Optional[str]): Filter by user ID
            start_time (Optional[datetime]): Filter by start time
            end_time (Optional[datetime]): Filter by end time
            limit (int): Maximum number of records to return
        
        Returns:
            list: List of session request records
        """
        connection = None
        try:
            connection = get_db_connection(self.db_name)
            if not connection:
                LOGGER_ERROR(f"Failed to get database connection for {self.db_name}")
                return []
            
            with connection.cursor() as cursor:
                # Build query
                where_conditions = []
                params = []
                
                if session_id:
                    where_conditions.append("session_id = %s")
                    params.append(session_id)
                
                if user_id:
                    where_conditions.append("user_id = %s")
                    params.append(user_id)
                
                if start_time:
                    where_conditions.append("created_at >= %s")
                    params.append(start_time)
                
                if end_time:
                    where_conditions.append("created_at <= %s")
                    params.append(end_time)
                
                where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
                
                query = f"""
                SELECT id, session_id, user_id, user_ip, user_agent, request_method,
                       request_path, request_params, request_headers, response_status,
                       response_time_ms, request_size, response_size, error_message,
                       session_start_time, session_end_time, is_active, created_at, updated_at
                FROM session_info
                {where_clause}
                ORDER BY created_at DESC
                LIMIT %s
                """
                
                params.append(limit)
                cursor.execute(query, params)
                
                results = cursor.fetchall()
                return results
                
        except Exception as e:
            LOGGER_ERROR(f"Failed to retrieve session requests: {str(e)}")
            return []
            
        finally:
            if connection:
                connection.close()
    
    def update_session_end(self, session_id: str, end_time: Optional[datetime] = None, is_active: bool = False) -> bool:
        """
        Update session end time and active status.
        
        Args:
            session_id (str): Session ID to update
            end_time (Optional[datetime]): Session end time (defaults to current time)
            is_active (bool): Whether session is still active
        
        Returns:
            bool: True if successful, False otherwise
        """
        connection = None
        try:
            connection = get_db_connection(self.db_name)
            if not connection:
                LOGGER_ERROR(f"Failed to get database connection for {self.db_name}")
                return False
            
            with connection.cursor() as cursor:
                end_time = end_time or datetime.now()
                
                update_sql = """
                UPDATE session_info 
                SET session_end_time = %s, is_active = %s, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = %s AND is_active = 1
                """
                
                cursor.execute(update_sql, (end_time, is_active, session_id))
                connection.commit()
                
                affected_rows = cursor.rowcount
                LOGGER_DEBUG(f"Updated {affected_rows} session records for session_id: {session_id}")
                return affected_rows > 0
                
        except Exception as e:
            LOGGER_ERROR(f"Failed to update session end: {str(e)}")
            if connection:
                connection.rollback()
            return False
            
        finally:
            if connection:
                connection.close()


# Global instance for easy access
session_info_manager = SessionInfoManager()
