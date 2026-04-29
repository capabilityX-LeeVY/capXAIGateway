"""
File Storage Manager
Handles uploaded file storage and management for session tracking.
"""

import os
import hashlib
import uuid
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from pathlib import Path
from django.core.files.uploadedfile import UploadedFile
from common.utils.logger import LOGGER_ERROR, LOGGER_DEBUG, LOGGER_INFO


class FileStorageManager:
    """
    File Storage Manager
    Handles secure file storage with deduplication and organization.
    """
    
    def __init__(self, base_storage_path: str = "uploads"):
        """
        Initialize FileStorageManager.
        
        Args:
            base_storage_path (str): Base directory for file storage
        """
        self.base_storage_path = base_storage_path
        self.ensure_storage_directories()
    
    def ensure_storage_directories(self):
        """Create necessary storage directories if they don't exist."""
        try:
            # Create main uploads directory
            os.makedirs(self.base_storage_path, exist_ok=True)
            
            # Create subdirectories by date for organization
            today = datetime.now().strftime('%Y/%m/%d')
            daily_path = os.path.join(self.base_storage_path, today)
            os.makedirs(daily_path, exist_ok=True)
            
        except Exception as e:
            LOGGER_ERROR(f"Failed to create storage directories: {str(e)}")
    
    def calculate_file_hash(self, file_content: bytes) -> str:
        """
        Calculate SHA-256 hash of file content.
        
        Args:
            file_content (bytes): File content as bytes
            
        Returns:
            str: SHA-256 hash string
        """
        return hashlib.sha256(file_content).hexdigest()
    
    def get_file_extension(self, filename: str) -> str:
        """
        Get file extension from filename.
        
        Args:
            filename (str): Original filename
            
        Returns:
            str: File extension with dot (e.g., '.jpg')
        """
        return Path(filename).suffix.lower() if filename else ''
    
    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename by removing/replacing unsafe characters.
        
        Args:
            filename (str): Original filename
            
        Returns:
            str: Sanitized filename
        """
        # Get filename without extension
        name = Path(filename).stem
        extension = Path(filename).suffix
        
        # Replace spaces and special characters
        # Keep only alphanumeric, underscore, hyphen, and dot
        import re
        name = re.sub(r'[^\w\-.]', '_', name)
        # Remove multiple consecutive underscores
        name = re.sub(r'_+', '_', name)
        # Remove leading/trailing underscores
        name = name.strip('_')
        
        return f"{name}{extension}"
    
    def generate_storage_path(self, original_filename: str, file_hash: str) -> str:
        """
        Generate organized storage path for file using original filename.
        
        Args:
            original_filename (str): Original filename
            file_hash (str): File hash for uniqueness when needed
            
        Returns:
            str: Generated storage path with original filename preserved
        """
        today = datetime.now().strftime('%Y/%m/%d')
        
        # Sanitize the original filename
        safe_filename = self.sanitize_filename(original_filename)
        
        # Use the sanitized original filename
        base_path = os.path.join(self.base_storage_path, today, safe_filename)
        
        # If file exists, check if it's the same content
        if os.path.exists(base_path):
            # File exists, we'll check hash in save_uploaded_file
            # For now, return the path with hash suffix as alternative
            name = Path(safe_filename).stem
            extension = Path(safe_filename).suffix
            return os.path.join(self.base_storage_path, today, f"{name}_{file_hash[:8]}{extension}")
        
        return base_path
    
    def save_uploaded_file(self, uploaded_file: UploadedFile) -> Optional[Dict[str, Any]]:
        """
        Save uploaded file to storage with metadata.
        Handles file name conflicts by checking content hash.
        
        Args:
            uploaded_file (UploadedFile): Django uploaded file object
            
        Returns:
            Optional[Dict[str, Any]]: File metadata or None if failed
        """
        try:
            # Read file content
            uploaded_file.seek(0)  # Reset file pointer
            file_content = uploaded_file.read()
            uploaded_file.seek(0)  # Reset again for potential reuse
            
            # Calculate file hash
            file_hash = self.calculate_file_hash(file_content)
            
            # Generate primary storage path (with original filename)
            today = datetime.now().strftime('%Y/%m/%d')
            safe_filename = self.sanitize_filename(uploaded_file.name)
            primary_path = os.path.join(self.base_storage_path, today, safe_filename)
            
            # Create directory if needed
            os.makedirs(os.path.dirname(primary_path), exist_ok=True)
            
            storage_path = primary_path
            
            # Check if file already exists
            if os.path.exists(primary_path):
                # File exists, check if it's the same content
                with open(primary_path, 'rb') as existing_file:
                    existing_content = existing_file.read()
                    existing_hash = self.calculate_file_hash(existing_content)
                
                if existing_hash == file_hash:
                    # Same content, reuse existing file
                    LOGGER_INFO(f"File with same content already exists, reusing: {primary_path}")
                else:
                    # Different content, add hash suffix to filename
                    name = Path(safe_filename).stem
                    extension = Path(safe_filename).suffix
                    storage_path = os.path.join(self.base_storage_path, today, f"{name}_{file_hash[:8]}{extension}")
                    
                    # Save with new filename
                    with open(storage_path, 'wb') as f:
                        f.write(file_content)
                    
                    LOGGER_INFO(f"File with different content saved with hash suffix: {storage_path}")
            else:
                # File doesn't exist, save it
                with open(storage_path, 'wb') as f:
                    f.write(file_content)
                
                LOGGER_INFO(f"File saved successfully: {storage_path}")
            
            # Return file metadata
            file_metadata = {
                'original_filename': uploaded_file.name,
                'stored_file_path': storage_path,
                'file_size': len(file_content),
                'file_type': uploaded_file.content_type,
                'file_hash': file_hash
            }
            
            return file_metadata
            
        except Exception as e:
            LOGGER_ERROR(f"Failed to save uploaded file: {str(e)}")
            return None
    
    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a stored file.
        
        Args:
            file_path (str): Path to the stored file
            
        Returns:
            Optional[Dict[str, Any]]: File information or None if not found
        """
        try:
            if not os.path.exists(file_path):
                return None
            
            stat = os.stat(file_path)
            
            return {
                'file_path': file_path,
                'file_size': stat.st_size,
                'created_time': datetime.fromtimestamp(stat.st_ctime),
                'modified_time': datetime.fromtimestamp(stat.st_mtime),
                'exists': True
            }
            
        except Exception as e:
            LOGGER_ERROR(f"Failed to get file info: {str(e)}")
            return None
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete a stored file.
        
        Args:
            file_path (str): Path to the file to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                LOGGER_INFO(f"File deleted successfully: {file_path}")
                return True
            else:
                LOGGER_ERROR(f"File not found for deletion: {file_path}")
                return False
                
        except Exception as e:
            LOGGER_ERROR(f"Failed to delete file: {str(e)}")
            return False
    
    def cleanup_old_files(self, days_old: int = 30) -> int:
        """
        Clean up files older than specified days.
        
        Args:
            days_old (int): Number of days after which files should be cleaned
            
        Returns:
            int: Number of files deleted
        """
        deleted_count = 0
        cutoff_time = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
        
        try:
            for root, dirs, files in os.walk(self.base_storage_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.getctime(file_path) < cutoff_time:
                        if self.delete_file(file_path):
                            deleted_count += 1
            
            LOGGER_INFO(f"Cleanup completed: {deleted_count} old files deleted")
            return deleted_count
            
        except Exception as e:
            LOGGER_ERROR(f"Failed to cleanup old files: {str(e)}")
            return deleted_count


# Global instance for easy access
file_storage_manager = FileStorageManager()