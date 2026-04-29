"""
Simple session tracker utility
Can be used directly in views to record session information.
"""

import time
import json
from datetime import datetime
from typing import Optional, Dict, Any
from django.http import HttpRequest
from django.core.files.uploadedfile import UploadedFile
from db.session_info_manager import session_info_manager
from gpt_gateway.utils.file_storage_manager import file_storage_manager


def get_client_ip(request: HttpRequest) -> Optional[str]:
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
        return ip
    
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip
    
    return request.META.get('REMOTE_ADDR')


def get_session_id(request: HttpRequest) -> str:
    """Get or create session ID."""
    if hasattr(request, 'session'):
        session_id = request.session.session_key
        if not session_id:
            request.session.create()
            session_id = request.session.session_key
        return session_id or f"anon_{int(time.time())}"
    
    return f"no_session_{int(time.time())}"


def get_request_params(request: HttpRequest) -> Optional[Dict]:
    """Get request parameters safely."""
    try:
        params = {}
        
        if request.GET:
            params['GET'] = dict(request.GET)
        
        if request.POST:
            # Filter sensitive data
            sensitive_fields = ['password', 'token', 'secret', 'key', 'auth']
            post_data = {}
            for key, value in request.POST.items():
                if not any(sensitive in key.lower() for sensitive in sensitive_fields):
                    post_data[key] = value
                else:
                    post_data[key] = '[FILTERED]'
            params['POST'] = post_data
        
        return params if params else None
    except:
        return None


def record_request(request: HttpRequest, response_status: int = 200, 
                  response_time_ms: Optional[int] = None, 
                  error_message: Optional[str] = None,
                  uploaded_file: Optional[UploadedFile] = None,
                  uploaded_files: Optional[list] = None) -> bool:
    """
    Record a session request.
    
    Args:
        request: Django request object
        response_status: HTTP response status code
        response_time_ms: Response time in milliseconds
        error_message: Error message if any
        uploaded_file: Uploaded file object if any (single file)
        uploaded_files: List of uploaded file objects (multiple files)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        session_id = get_session_id(request)
        user_ip = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        request_params = get_request_params(request)
        request_size = int(request.META.get('CONTENT_LENGTH', 0)) or None
        
        # Get user ID if authenticated
        user_id = None
        if hasattr(request, 'user') and hasattr(request.user, 'id') and request.user.is_authenticated:
            user_id = str(request.user.id)
        
        # Handle file uploads (single or multiple)
        file_metadata = {}
        files_to_save = []
        
        if uploaded_files:
            # Multiple files
            files_to_save = uploaded_files
        elif uploaded_file:
            # Single file
            files_to_save = [uploaded_file]
        
        if files_to_save:
            # Save all files and collect metadata
            all_filenames = []
            all_paths = []
            all_sizes = []
            all_types = []
            all_hashes = []
            
            for file in files_to_save:
                saved_file_info = file_storage_manager.save_uploaded_file(file)
                if saved_file_info:
                    all_filenames.append(saved_file_info['original_filename'])
                    all_paths.append(saved_file_info['stored_file_path'])
                    all_sizes.append(str(saved_file_info['file_size']))
                    all_types.append(saved_file_info['file_type'])
                    all_hashes.append(saved_file_info['file_hash'])
            
            # Combine multiple file info with separator
            # Note: file_hash field is limited to 64 chars, so only store first file's hash
            if all_filenames:
                file_metadata = {
                    'original_filename': ' | '.join(all_filenames),
                    'stored_file_path': ' | '.join(all_paths),
                    'file_size': sum(int(s) for s in all_sizes) if all_sizes else None,
                    'file_type': all_types[0] if len(all_types) == 1 else 'multiple',  # DB field limited to 100 chars
                    'file_hash': all_hashes[0] if all_hashes else None  # DB field limited to 64 chars, store first only
                }
        
        success = session_info_manager.record_session_request(
            session_id=session_id,
            user_id=user_id,
            user_ip=user_ip,
            user_agent=user_agent,
            request_method=request.method or 'GET',
            request_path=request.path,
            request_params=request_params,
            response_status=response_status,
            response_time_ms=response_time_ms,
            request_size=request_size,
            error_message=error_message,
            session_start_time=datetime.now(),
            is_active=True,
            # File-related fields
            uploaded_file_name=file_metadata.get('original_filename'),
            stored_file_path=file_metadata.get('stored_file_path'),
            file_size=file_metadata.get('file_size'),
            file_type=file_metadata.get('file_type'),
            file_hash=file_metadata.get('file_hash')
        )
        
        return success
        
    except Exception as e:
        print(f"Error recording session request: {str(e)}")
        return False


class SessionTracker:
    """Context manager for tracking session requests with timing."""
    
    def __init__(self, request: HttpRequest):
        self.request = request
        self.start_time = None
        self.response_status = 200
        self.error_message = None
        self.uploaded_file = None
        self.uploaded_files = []  # Support multiple files
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.response_status = 500
            self.error_message = str(exc_val)
        
        response_time_ms = int((time.time() - self.start_time) * 1000) if self.start_time else None
        
        # Determine which file(s) to record
        uploaded_file = None
        uploaded_files = None
        
        if self.uploaded_files:
            # Multiple files
            uploaded_files = self.uploaded_files
        elif self.uploaded_file:
            # Single file
            uploaded_file = self.uploaded_file
        
        record_request(
            self.request, 
            self.response_status, 
            response_time_ms, 
            self.error_message,
            uploaded_file,
            uploaded_files
        )
        
        return False  # Don't suppress exceptions
    
    def set_response_status(self, status: int):
        """Set response status code."""
        self.response_status = status
    
    def set_error_message(self, message: str):
        """Set error message."""
        self.error_message = message
    
    def set_uploaded_file(self, uploaded_file: UploadedFile):
        """Set uploaded file for tracking (single file)."""
        self.uploaded_file = uploaded_file
    
    def set_uploaded_files(self, uploaded_files: list):
        """Set multiple uploaded files for tracking."""
        self.uploaded_files = uploaded_files if uploaded_files else []
