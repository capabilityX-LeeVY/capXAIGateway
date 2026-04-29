"""
JIRA Connection Manager
Manages JIRA connections and configuration for the application.
"""

import json
import os
from typing import Optional, Dict, Any
from jira import JIRA
from common.utils.logger import LOGGER_ERROR, LOGGER_DEBUG, LOGGER_INFO


class JiraConnectionManager:
    """
    JIRA Connection Manager - Singleton pattern
    Manages JIRA connections and configuration.
    """
    _instance: Optional['JiraConnectionManager'] = None
    _jira_config: Dict[str, Any] = {}
    _jira_client: Optional[JIRA] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JiraConnectionManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._load_jira_config()
        self._initialized = True
    
    def _load_jira_config(self):
        """Load JIRA configuration from config file"""
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                'config', 'jira_config.json'
            )
            
            LOGGER_DEBUG(f"Loading JIRA configs from: {config_path}")
            with open(config_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                self._jira_config = settings.get("jira", {})
                
            LOGGER_DEBUG("JIRA configuration loaded successfully")
                
        except Exception as e:
            LOGGER_ERROR(f"Failed to load JIRA configuration: {str(e)}")
            self._jira_config = {}
    
    def get_config(self, key: str = None) -> Any:
        """
        Get JIRA configuration value.
        
        Args:
            key (str): Configuration key. If None, returns entire config
            
        Returns:
            Any: Configuration value or entire config dict
        """
        if key is None:
            return self._jira_config
        return self._jira_config.get(key)
    
    def is_enabled(self) -> bool:
        """Check if JIRA integration is enabled."""
        return self._jira_config.get('enabled', False)
    
    def get_client(self) -> Optional[JIRA]:
        """
        Get JIRA client instance.
        
        Returns:
            Optional[JIRA]: JIRA client or None if configuration is invalid
        """
        if not self.is_enabled():
            LOGGER_ERROR("JIRA integration is disabled")
            return None
        
        if self._jira_client is None:
            try:
                server = self._jira_config.get('server')
                token = self._jira_config.get('token')
                
                if not server or not token:
                    LOGGER_ERROR("JIRA server or token not configured")
                    return None
                
                self._jira_client = JIRA(
                    server=server,
                    token_auth=token,
                    options={'headers': {'Connection': 'close'}}
                )
                LOGGER_INFO("JIRA client initialized successfully")
                
            except Exception as e:
                LOGGER_ERROR(f"Failed to initialize JIRA client: {str(e)}")
                return None
        
        return self._jira_client
    
    def test_connection(self) -> bool:
        """
        Test JIRA connection.
        
        Returns:
            bool: True if connection is successful, False otherwise
        """
        try:
            client = self.get_client()
            if client is None:
                return False
            
            # Test connection by getting current user info
            user = client.current_user()
            LOGGER_INFO(f"JIRA connection test successful. Current user: {user}")
            return True
            
        except Exception as e:
            LOGGER_ERROR(f"JIRA connection test failed: {str(e)}")
            return False


# Global singleton instance
jira_connection_manager = JiraConnectionManager()