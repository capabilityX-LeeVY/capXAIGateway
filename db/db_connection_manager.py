"""
Database Connection Manager
Manages database connections for different databases across the application.
"""

import os
import pymysql
import json
from typing import Optional, Dict, Any
from common.utils.logger import LOGGER_ERROR, LOGGER_DEBUG

# Get the project root directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_CONFIG_PATH = os.path.join(PROJECT_ROOT, 'config', 'db_config.json')


class DBConnectionManager:
    """
    Database Connection Manager - Singleton pattern
    Manages database connections for different databases.
    """
    _instance: Optional['DBConnectionManager'] = None
    _db_configs: Dict[str, Dict[str, Any]] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DBConnectionManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._load_db_configs()
        self._initialized = True
    
    def _load_db_configs(self):
        """Load all database configurations from db_config.json"""
        try:
            LOGGER_DEBUG(f"Loading database configs from: {DB_CONFIG_PATH}")
            with open(DB_CONFIG_PATH, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                self._db_configs = settings.get("dbConfig", {})
                
            LOGGER_DEBUG(f"Loaded {len(self._db_configs)} database configurations")
                
        except Exception as e:
            LOGGER_ERROR(f"Failed to load database configurations: {str(e)}")
            self._db_configs = {}
    
    def get_db_config(self, db_name: str) -> Dict[str, Any]:
        """
        Get database configuration by name.
        
        Args:
            db_name (str): Database name (e.g., 'GT', 'TEST', 'PROD')
        
        Returns:
            Dict[str, Any]: Database configuration or empty dict if not found
        """
        return self._db_configs.get(db_name, {})
    
    def get_connection(self, db_name: str) -> Optional[pymysql.Connection]:
        """
        Get database connection for specified database.
        
        Args:
            db_name (str): Database name (e.g., 'GT', 'TEST', 'PROD')
        
        Returns:
            Optional[pymysql.Connection]: Database connection or None if failed
        """
        config = self.get_db_config(db_name)
        if not config:
            LOGGER_ERROR(f"No configuration found for database: {db_name}")
            return None
        
        try:
            connection = pymysql.connect(**config)
            LOGGER_DEBUG(f"Successfully connected to database: {db_name}")
            return connection
            
        except pymysql.Error as e:
            LOGGER_ERROR(f"Failed to connect to database '{db_name}': {e}")
            return None


# Global singleton instance for easy access
db_connection_manager = DBConnectionManager()

# Direct access to the connection method for convenience
get_db_connection = db_connection_manager.get_connection
