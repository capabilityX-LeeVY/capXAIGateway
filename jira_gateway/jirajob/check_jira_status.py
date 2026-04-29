import os
import sys
import time
import socket
import threading
import requests
import logging
import json
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from threading import Lock
from collections import deque
# 注释掉直接的JIRA导入，改用HTTP API
# from jira import JIRA

# 添加父目录到路径以便导入项目模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from jira_gateway.tojirabug import MysqlConnection, MessageBot, TeamsJiraIssueReporter

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class MCPClientPool:
    """
    MCP Client Pool Manager - manages multiple MCP clients for parallel bug verification
    """
    
    def __init__(self, config_path=None):
        """
        Initialize MCP client pool
        
        Args:
            config_path: Path to MCP clients configuration file
        """
        self.lock = Lock()
        self.clients = {}  # {client_id: client_info}
        self.active_tasks = {}  # {client_id: {jira_id, start_time}}
        self.task_queue = deque()  # Queue of pending tasks
        self.task_history = {}  # {jira_id: {client_id, status, start_time, end_time}}
        self.task_timeout = 1200  # 20 minutes timeout for tasks
        self.scheduling_config = {}
        self.health_check_interval = 30  # seconds
        self.health_check_timeout = 2  # seconds
        
        # Load configuration
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'config', 'mcp_clients_config.json'
            )
        
        self.load_config(config_path)
        # Load health check settings from scheduling config if provided
        self.health_check_interval = self.scheduling_config.get('health_check_interval_seconds', 30)
        self.health_check_timeout = self.scheduling_config.get('health_check_timeout_seconds', 2)
        logger.info(f"🔧 MCP Client Pool initialized with {len(self.clients)} clients")
    
    def load_config(self, config_path):
        """Load MCP clients configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            for client_config in config.get('mcp_clients', []):
                if client_config.get('enabled', True):
                    client_id = client_config['id']
                    self.clients[client_id] = {
                        'id': client_id,
                        'host': client_config['host'],
                        'port': client_config['port'],
                        'url': f"http://{client_config['host']}:{client_config['port']}/execute_command",
                        'description': client_config.get('description', ''),
                        'platform': client_config.get('platform', ''),  # Add platform field
                        'priority': client_config.get('priority', 99),
                        'max_concurrent_tasks': client_config.get('max_concurrent_tasks', 1),
                        'status': 'idle',  # idle, busy, error
                        'last_heartbeat': None,
                        'error_count': 0
                    }
                    logger.info(f"  ✅ Loaded client: {client_id} ({client_config['host']}:{client_config['port']})")
            
            self.scheduling_config = config.get('scheduling', {})
            logger.info(f"📋 Scheduling strategy: {self.scheduling_config.get('strategy', 'round_robin')}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load MCP client config: {e}")
            # Fallback to single default client
            self.clients = {
                'mcp-default': {
                    'id': 'mcp-default',
                    'host': '10.140.216.88',
                    'port': 9000,
                    'url': 'http://10.140.216.88:9000/execute_command',
                    'description': 'Default MCP Client',
                    'priority': 1,
                    'max_concurrent_tasks': 1,
                    'status': 'idle',
                    'last_heartbeat': None,
                    'error_count': 0
                }
            }
            self.scheduling_config = {}

    def _should_check_health(self, last_heartbeat):
        """Determine whether to perform a health check for the client"""
        if last_heartbeat is None:
            return True
        return (time.time() - last_heartbeat) >= self.health_check_interval

    def _is_client_reachable(self, host, port):
        """Lightweight TCP connectivity check"""
        try:
            with socket.create_connection((host, port), timeout=self.health_check_timeout):
                return True
        except Exception:
            return False

    def _refresh_client_status(self, client_id):
        """Refresh client status via health check, return True if reachable"""
        with self.lock:
            client = self.clients.get(client_id)
            if not client:
                return False
            status = client['status']
            host = client['host']
            port = client['port']
            last_heartbeat = client.get('last_heartbeat')

        # Only check health for idle/error clients to avoid interfering with active tasks
        if status not in ['idle', 'error']:
            return True

        if not self._should_check_health(last_heartbeat):
            return status != 'error'

        reachable = self._is_client_reachable(host, port)

        with self.lock:
            client = self.clients.get(client_id)
            if not client:
                return False
            if reachable:
                client['last_heartbeat'] = time.time()
                client['error_count'] = 0
                if client['status'] == 'error':
                    client['status'] = 'idle'
                    logger.info(f"✅ MCP client {client_id} recovered and is now idle")
            else:
                client['last_heartbeat'] = time.time()
                client['error_count'] = client.get('error_count', 0) + 1
                if client['status'] in ['idle', 'error']:
                    client['status'] = 'error'
                logger.warning(f"❌ MCP client {client_id} unreachable (host={host}, port={port})")

        return reachable
    
    def get_available_client(self, platform=None):
        """
        Get an available (idle) MCP client for task assignment
        
        Args:
            platform: Optional platform filter (e.g., "Windows", "Mac", "macOS")
                     Supports case-insensitive matching and aliases (Mac/macOS)
        
        Returns:
            client_info dict or None if no client available
        """
        # Normalize platform name for matching
        normalized_platform = None
        if platform:
            platform_lower = platform.lower()
            if platform_lower in ['mac', 'macos']:
                normalized_platform = 'mac'  # Unified name for Mac
            elif platform_lower in ['windows', 'win']:
                normalized_platform = 'windows'
            else:
                normalized_platform = platform_lower
            logger.debug(f"🔍 Looking for client with platform: {platform} (normalized: {normalized_platform})")
        
        # Sort clients by priority (lower number = higher priority)
        with self.lock:
            sorted_client_ids = [c['id'] for c in sorted(
                self.clients.values(),
                key=lambda x: (x['priority'], x['error_count'])
            )]

        for client_id in sorted_client_ids:
            # Refresh health before selection
            if not self._refresh_client_status(client_id):
                continue

            with self.lock:
                client = self.clients.get(client_id)
                if not client:
                    continue
                
                # Check platform compatibility if platform is specified
                if normalized_platform:
                    client_platform = client.get('platform', '').lower()
                    # Normalize client platform
                    if client_platform in ['mac', 'macos']:
                        client_platform = 'mac'
                    elif client_platform in ['windows', 'win']:
                        client_platform = 'windows'
                    
                    if client_platform != normalized_platform:
                        logger.debug(f"⏭️ Skipping {client_id}: platform mismatch (need {normalized_platform}, got {client_platform})")
                        continue
                
                current_status = client['status']
                logger.debug(f"🔍 Checking {client_id}: status={current_status}, platform={client.get('platform', 'N/A')}, in_active_tasks={client_id in self.active_tasks}")
                # Check if client is idle and not at max concurrent tasks
                if client['status'] == 'idle' and client_id not in self.active_tasks:
                    logger.debug(f"🎯 Selected available client: {client_id} (platform: {client.get('platform', 'N/A')})")
                    # Immediately mark as reserved to prevent race condition
                    self.clients[client_id]['status'] = 'reserved'
                    logger.debug(f"✅ Status changed: {client_id} -> reserved")
                    return client

        if normalized_platform:
            logger.warning(f"⏳ No available client found for platform '{platform}'. Active tasks: {list(self.active_tasks.keys())}")
        else:
            logger.debug(f"⏳ No available client found. Active tasks: {list(self.active_tasks.keys())}")
        return None
    
    def assign_task(self, client_id, jira_id, bug_info):
        """
        Assign a task to a specific client
        
        Args:
            client_id: MCP client ID
            jira_id: JIRA issue ID
            bug_info: Bug information dictionary
        """
        with self.lock:
            # Check if this jira_id is already being processed by another client
            for cid, task in self.active_tasks.items():
                if task['jira_id'] == jira_id:
                    logger.warning(f"⚠️ Task {jira_id} already being processed by {cid}, skipping assignment to {client_id}")
                    return False
            
            if client_id in self.clients:
                old_status = self.clients[client_id]['status']
                self.active_tasks[client_id] = {
                    'jira_id': jira_id,
                    'bug_info': bug_info,
                    'start_time': datetime.now(),
                    'status': 'running'
                }
                # Change from 'reserved' or 'idle' to 'busy'
                self.clients[client_id]['status'] = 'busy'
                logger.debug(f"📝 Status changed: {client_id} {old_status} -> busy")
                
                # Record in history
                self.task_history[jira_id] = {
                    'client_id': client_id,
                    'status': 'running',
                    'start_time': datetime.now(),
                    'end_time': None
                }
                
                logger.info(f"📌 Task assigned: {jira_id} → {client_id} ({self.clients[client_id]['host']})")
                logger.debug(f"✅ active_tasks now: {list(self.active_tasks.keys())}")
                return True
            return False
    
    def unreserve_client(self, client_id):
        """
        Release a reserved client back to idle if task assignment fails
        
        Args:
            client_id: MCP client ID
        """
        with self.lock:
            if client_id in self.clients and self.clients[client_id]['status'] == 'reserved':
                self.clients[client_id]['status'] = 'idle'
                logger.debug(f"🔓 Client {client_id} unreserved (back to idle)")
                return True
            return False
    
    def add_to_queue(self, jira_id, bug_info, message, message_type='bug_status_change'):
        """
        Add a task to the queue when no client is available
        
        Args:
            jira_id: JIRA issue ID
            bug_info: Bug information dictionary
            message: Message content
            message_type: Message type
        """
        with self.lock:
            # Check if task is already being processed
            for client_id, task in self.active_tasks.items():
                if task['jira_id'] == jira_id:
                    logger.debug(f"⏭️ Task {jira_id} already being processed by {client_id}, skipping queue add")
                    return False
            
            # Check if task already in queue
            for task in self.task_queue:
                if task['jira_id'] == jira_id:
                    logger.debug(f"⏭️ Task {jira_id} already in queue, skipping")
                    return False
            
            task = {
                'jira_id': jira_id,
                'bug_info': bug_info,
                'message': message,
                'message_type': message_type,
                'queued_at': datetime.now(),
                'retry_count': 0
            }
            self.task_queue.append(task)
            logger.info(f"📥 Task queued: {jira_id} (queue size: {len(self.task_queue)})")
            return True
    
    def release_client(self, client_id, jira_id, status='completed'):
        """
        Release a client after task completion and process queue
        
        Args:
            client_id: MCP client ID
            jira_id: JIRA issue ID
            status: Task completion status (completed, failed, timeout)
        """
        with self.lock:
            if client_id in self.active_tasks:
                task = self.active_tasks.pop(client_id)
                self.clients[client_id]['status'] = 'idle'
                
                # Update history
                if jira_id in self.task_history:
                    self.task_history[jira_id]['status'] = status
                    self.task_history[jira_id]['end_time'] = datetime.now()
                    duration = (self.task_history[jira_id]['end_time'] - 
                               self.task_history[jira_id]['start_time']).total_seconds()
                    
                    logger.info(f"✅ Client released: {client_id} | Task: {jira_id} | "
                              f"Status: {status} | Duration: {duration:.1f}s")
                
                # Check if there are queued tasks and process them
                if len(self.task_queue) > 0:
                    logger.info(f"🔄 Client {client_id} released, checking queue ({len(self.task_queue)} tasks pending)")
                    # Return client info for queue processing
                    return self.clients[client_id]
                
                return True
            return False
    
    def get_client_by_id(self, client_id):
        """Get client info by ID"""
        return self.clients.get(client_id)
    
    def get_task_info(self, jira_id):
        """Get task information from history"""
        return self.task_history.get(jira_id)
    
    def get_pool_status(self):
        """Get current pool status summary"""
        with self.lock:
            idle_count = sum(1 for c in self.clients.values() if c['status'] == 'idle')
            busy_count = sum(1 for c in self.clients.values() if c['status'] == 'busy')
            
            return {
                'total_clients': len(self.clients),
                'idle_clients': idle_count,
                'busy_clients': busy_count,
                'active_tasks': len(self.active_tasks),
                'queued_tasks': len(self.task_queue),
                'clients': {cid: c['status'] for cid, c in self.clients.items()}
            }
    
    def check_and_release_timeout_tasks(self):
        """Check for timeout tasks and automatically release clients"""
        now = datetime.now()
        timeout_tasks = []
        
        with self.lock:
            for client_id, task in list(self.active_tasks.items()):
                duration = (now - task['start_time']).total_seconds()
                if duration > self.task_timeout:
                    timeout_tasks.append((client_id, task['jira_id'], duration))
        
        # Release timeout tasks (outside lock to avoid deadlock)
        for client_id, jira_id, duration in timeout_tasks:
            logger.warning(f"⏰ Task timeout detected: {jira_id} on {client_id} (duration: {duration:.1f}s > {self.task_timeout}s)")
            self.release_client(client_id, jira_id, status='timeout')
            logger.info(f"🔄 Auto-released {client_id} due to timeout")
        
        # Process queue if there are timeout releases and queued tasks
        if timeout_tasks and len(self.task_queue) > 0:
            logger.info(f"🚀 Processing queue after timeout cleanup ({len(self.task_queue)} tasks pending)")
            # Return timeout count and queue size for caller to process
            return len(timeout_tasks)
        
        return len(timeout_tasks)
    
    def process_queue(self, max_tasks=None):
        """
        Process queued tasks by assigning them to available clients
        
        Args:
            max_tasks: Maximum number of tasks to process (None = process all)
        
        Returns:
            List of (client, task) tuples for tasks successfully assigned
        """
        assigned_tasks = []
        max_tasks = max_tasks or len(self.task_queue)
        
        while self.task_queue and len(assigned_tasks) < max_tasks:
            # Peek at the next task to get platform info
            with self.lock:
                if not self.task_queue:
                    break
                next_task = self.task_queue[0]  # Peek without removing
            
            # Get platform from task's bug_info
            platform = next_task.get('bug_info', {}).get('platform')
            
            # Get available client matching the platform
            client = self.get_available_client(platform=platform)
            if client is None:
                logger.debug(f"⏸️ No available clients for platform '{platform}', stopping queue processing ({len(self.task_queue)} tasks remaining)")
                break
            
            # Now actually dequeue the task
            with self.lock:
                if not self.task_queue:
                    break
                task = self.task_queue.popleft()
            
            jira_id = task['jira_id']
            bug_info = task['bug_info']
            
            # Calculate queue wait time
            wait_time = (datetime.now() - task['queued_at']).total_seconds()
            logger.info(f"📤 Processing queued task: {jira_id} (platform: {platform}, waited {wait_time:.1f}s)")
            
            # Assign task to client
            client_id = client['id']
            if self.assign_task(client_id, jira_id, bug_info):
                assigned_tasks.append((client, task))
            else:
                # Re-queue if assignment failed
                logger.warning(f"⚠️ Failed to assign {jira_id}, re-queuing")
                with self.lock:
                    task['retry_count'] += 1
                    if task['retry_count'] < 3:  # Max 3 retries
                        self.task_queue.append(task)
                    else:
                        logger.error(f"❌ Task {jira_id} exceeded max retries, dropping")
        
        if assigned_tasks:
            logger.info(f"✅ Processed {len(assigned_tasks)} tasks from queue ({len(self.task_queue)} remaining)")
        
        return assigned_tasks


class JiraStatusChecker:
    """
    Class for periodic detection of JIRA bug status changes
    Enhanced with multi-client parallel verification support
    """
    
    def __init__(self):
        # HTTP API configuration (using local Django service)
        self.api_base_url = 'http://localhost:9912'
        self.jira_api_url = f'{self.api_base_url}/jira'
        self.verification_api_url = 'https://capx.capx.com/run_testcase'  # External verification endpoint
        
        # Django server configuration (for MCP callback)
        # ⚠️ IMPORTANT: This IP must be reachable from MCP client (10.140.216.88)
        self.django_server_host = '10.224.118.63'  # Your Django server's IP
        self.django_server_port = 9912
        self.django_callback_url = f'http://{self.django_server_host}:{self.django_server_port}/jira/mcp_callback/'
        
        # Original JIRA connection configuration (kept as backup)
        self.jira_url = 'https://jira-eng-gpk2.capx.com/jira'
        self.jira_token = 'NDcwMjEwNDU0Olkunv7VJrh+a0YGT9kq8f4tQI5G'
        self.jira_client = None  # No longer using JIRA client directly
        
        # Database connection configuration
        self.db_host = 'capx-dev.capx.com'
        self.db_port = 3306
        self.db_user = 'test'
        self.db_password = 'pass'
        self.db_name = 'issue_db'
        self.db_connection = None
        
        # Message bot
        self.message_bot = MessageBot()
        
        # MCP Client Pool (multi-client support)
        self.mcp_pool = MCPClientPool()
        
        # Backward compatibility: keep original single client config
        self.mcp_client_host = '10.140.216.88'
        self.mcp_client_port = 9000
        self.mcp_client_url = f'http://{self.mcp_client_host}:{self.mcp_client_port}/execute_command'

        # Check interval (seconds) - default check every 8 hours
        self.check_interval = 60

        # Scheduler
        self.scheduler = None
        
        # Status tracking cache
        self.bug_status_cache = {}  # {jira_id: {'jira_status': 'NEW', 'last_check': datetime, 'db_id': 'xxx'}}
        self.processed_bugs = set()  # Set of processed bug IDs
        
        # Running status
        self.is_running = True 
        
        # API call rate control
        self.api_call_delay = 2  # 5-second interval between API calls (more conservative)
        self.last_api_call = None
        self.consecutive_429_errors = 0  # Consecutive 429 error count
        self.max_retries = 3  # Maximum retry attempts
        
        # Initialize connections
        self.initialize_connections()
        self.start_status_check_scheduler()
    
    def initialize_connections(self):
        """Initialize HTTP API and database connections"""
        try:
            # Test HTTP API connection
            health_response = requests.get(f'{self.jira_api_url}/health/', timeout=10)
            if health_response.status_code == 200:
                logger.info("✅ JIRA HTTP API connection successful")
            else:
                logger.warning(f"⚠️ JIRA HTTP API connection abnormal: {health_response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ JIRA HTTP API connection failed: {e}")

        try:
            # Initialize database connection
            self.db_connection = MysqlConnection(
                self.db_host, 
                self.db_port, 
                self.db_user, 
                self.db_password, 
                self.db_name
            )
            logger.info("✅ Database connection initialization successful")
        except Exception as e:
            logger.error(f"❌ Database connection initialization failed: {e}")
    
    def _wait_for_api_rate_limit(self):
        """API call rate control to avoid triggering JIRA rate limits"""
        if self.last_api_call is not None:
            elapsed = time.time() - self.last_api_call
            
            # Base delay + dynamic adjustment based on consecutive 429 errors
            dynamic_delay = self.api_call_delay + (self.consecutive_429_errors * 2)
            
            if elapsed < dynamic_delay:
                sleep_time = dynamic_delay - elapsed
                logger.debug(f"⏱️ API rate control: waiting {sleep_time:.1f} seconds (429 error count: {self.consecutive_429_errors})")
                time.sleep(sleep_time)
        
        self.last_api_call = time.time()
    
    def _safe_jira_call(self, jira_id):
        """Safely retrieve JIRA information via HTTP API"""
        for attempt in range(self.max_retries):
            try:
                self._wait_for_api_rate_limit()
                
                # Use HTTP API to get issue details
                url = f'{self.jira_api_url}/issue/{jira_id}/'
                response = requests.get(url, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        issue_data = data.get('issue', {})
                        
                        # Successful call, reset 429 error count
                        if self.consecutive_429_errors > 0:
                            logger.info(f"✅ HTTP API call recovered, reset 429 error count")
                            self.consecutive_429_errors = 0
                        
                        return issue_data
                    else:
                        logger.error(f"❌ HTTP API returned failure: {data.get('message', 'Unknown error')}")
                        return None
                        
                elif response.status_code == 429:
                    self.consecutive_429_errors += 1
                    retry_delay = 30 + (attempt * 15)  # 30, 45, 60 seconds
                    logger.warning(f"⚠️ HTTP API encountered 429 error (attempt {attempt+1}), waiting {retry_delay} seconds before retry...")
                    time.sleep(retry_delay)
                    continue
                    
                elif response.status_code == 404:
                    logger.warning(f"⚠️ Issue {jira_id} does not exist or no access permission")
                    return None
                    
                else:
                    logger.error(f"❌ HTTP API call failed: {response.status_code} - {response.text}")
                    return None
                
            except requests.exceptions.Timeout:
                logger.warning(f"⚠️ HTTP API timeout (attempt {attempt+1})")
                if attempt < self.max_retries - 1:
                    time.sleep(10)
                    continue
                else:
                    logger.error(f"❌ Still timeout after {self.max_retries} retries: {jira_id}")
                    return None
                    
            except Exception as e:
                logger.error(f"❌ HTTP API call exception: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(10)
                    continue
                else:
                    break
        
        # All retries failed
        logger.error(f"❌ Still failed after {self.max_retries} retries: {jira_id}")
        return None
    
    def get_new_and_existing_bugs(self):
        """Get new bugs and existing bugs, handle separately"""
        try:
            if not self.db_connection:
                logger.error("❌ Database connection not initialized")
                return [], []
                
            sql = """
                SELECT jiraID, title, createDate, affectVersion, platform, status, 
                       type, testSuite, testCase, testStep
                FROM issue_by_capx
                WHERE testStep IS NOT NULL AND testStep != ''
                ORDER BY createDate DESC
            """
            results, columns = self.db_connection.Query(sql)
            
            new_bugs = []
            existing_bugs = []
            current_bug_ids = set()
            
            for row in results:
                jira_id = row[0]
                current_bug_ids.add(jira_id)
                
                bug = {
                    'jiraID': jira_id,
                    'title': row[1],
                    'createDate': row[2],
                    'affectVersion': row[3],
                    'platform': row[4],
                    'status': row[5],  # Use 'status' for consistency
                    'db_status': row[5],  # Keep db_status for backward compatibility
                    'type': row[6],
                    'testSuite': row[7],
                    'testCase': row[8],
                    'testStep': row[9]
                }
                
                # If this bug hasn't been processed before, consider it a new bug
                if jira_id not in self.processed_bugs:
                    new_bugs.append(bug)
                    self.processed_bugs.add(jira_id)
                else:
                    existing_bugs.append(bug)
            
            # Clean up deleted bugs (if some bugs were deleted from database)
            deleted_bugs = self.processed_bugs - current_bug_ids
            if deleted_bugs:
                logger.info(f"🗑️ Found {len(deleted_bugs)} deleted bugs, removing from cache")
                for bug_id in deleted_bugs:
                    self.processed_bugs.discard(bug_id)
                    self.bug_status_cache.pop(bug_id, None)
            
            logger.info(f"📊 Retrieved {len(results)} bugs from database (new:{len(new_bugs)}, existing:{len(existing_bugs)})")
            
            # Debug: Print details of all bugs for troubleshooting
            logger.debug("🔍 Bug categorization details:")
            for bug in new_bugs:
                logger.debug(f"  🆕 New: {bug['jiraID']} - DB Status: {bug.get('db_status', 'Unknown')}")
            for bug in existing_bugs:
                logger.debug(f"  📋 Existing: {bug['jiraID']} - DB Status: {bug.get('db_status', 'Unknown')}")
            logger.debug(f"  🧠 Total processed bugs in memory: {len(self.processed_bugs)}")
            logger.debug(f"  📝 Current bug IDs from DB: {sorted(current_bug_ids)}")
            
            return new_bugs, existing_bugs
            
        except Exception as e:
            logger.error(f"❌ Failed to get bug list: {e}")
            return [], []
    
    def check_and_cache_jira_status(self, jira_id, force_check=False, bug=None):
        """Check JIRA status and cache results
        
        Args:
            jira_id: JIRA issue ID
            force_check: Whether to force check (set to True for new bugs, False for existing bugs to let method auto-determine cache expiry)
            bug: Optional bug dictionary from database (contains type, testSuite, testCase, testStep, etc.)
        
        Returns:
            Status info dictionary containing jira_status, resolution, assignee, updated, last_check
        """
        try:
            current_time = datetime.now()
            
            # Cache strategy:
            # 1. If force_check=True (new bug) -> Force query from JIRA
            # 2. If force_check=False (existing bug) -> Use shorter cache for active monitoring (2 minutes instead of 5)
            if not force_check and jira_id in self.bug_status_cache:
                cached = self.bug_status_cache[jira_id]
                # Shorter cache for better status change detection (2 minutes for active bugs)
                cache_age_seconds = (current_time - cached['last_check']).total_seconds()
                cache_threshold = 30  # 2 minutes for more responsive monitoring
                if cache_age_seconds < cache_threshold:
                    logger.debug(f"🔄 Using cached status: {jira_id} - {cached['jira_status']} (cached {int(cache_age_seconds)} seconds ago)")
                    return cached
                else:
                    logger.debug(f"⏰ Cache expired: {jira_id} (expired {int(cache_age_seconds-cache_threshold)} seconds ago), re-querying JIRA")
            
            # Get latest status from HTTP API
            issue_data = self._safe_jira_call(jira_id)
            if not issue_data:
                return None
            
            # Extract status information from HTTP API response (adapt to our API format)
            current_status = issue_data.get('status', 'Unknown')
            resolution = issue_data.get('resolution')
            assignee = issue_data.get('assignee')
            reporter = issue_data.get('reporter')
            priority = issue_data.get('priority')
            issue_type = issue_data.get('issue_type')
            
            # Extract more detailed information
            summary = issue_data.get('summary', '') or 'No Summary Available'
            description = issue_data.get('description', '') or 'No Description Available'
            created = issue_data.get('created')
            updated = issue_data.get('updated')
            
            # Extract version and component information
            affects_versions = issue_data.get('affects_versions', [])
            fix_versions = issue_data.get('fix_versions', [])
            components = issue_data.get('components', [])
            labels = issue_data.get('labels', [])
            
            # Extract custom fields
            custom_fields = issue_data.get('custom_fields', {})
            
            # Build complete status information
            status_info = {
                # Basic status information (maintain backward compatibility)
                'jira_status': current_status,
                'resolution': resolution,
                'assignee': assignee,
                'updated': updated,
                'last_check': current_time,
                
                # Extended detailed information
                'key': jira_id,
                'summary': summary,
                'description': description,
                'reporter': reporter,
                'priority': priority,
                'issue_type': issue_type,
                'created': created,
                'affects_versions': affects_versions,
                'fix_versions': fix_versions,
                'components': components,
                'labels': labels,
                'custom_fields': custom_fields,
                'url': f'https://jira-eng-gpk2.capx.com/jira/browse/{jira_id}'
            }
            
            # Update cache and record status changes
            # For first-time checks, use database status as old_status if cache is empty
            old_status = self.bug_status_cache.get(jira_id, {}).get('jira_status')
            if not old_status and bug:
                # Use database status as baseline for new bugs
                old_status = bug.get('db_status') or bug.get('status')
                logger.debug(f"📊 Using database status as old_status for {jira_id}: {old_status}")
            
            self.bug_status_cache[jira_id] = status_info
            
            # Check if there are important status changes that need notification
            if old_status and old_status != current_status:
                logger.info(f"🔄 Status changed: {jira_id} {old_status} -> {current_status}")
                
                # Immediately update database with new status
                if self.db_connection:
                    try:
                        sql = """
                            UPDATE issue_by_capx
                            SET status = %s
                            WHERE jiraID = %s
                        """
                        success = self.db_connection.ExecuteWithData(sql, (current_status, jira_id))
                        if success:
                            logger.info(f"✅ Database updated immediately: {jira_id} -> {current_status}")
                        else:
                            logger.warning(f"⚠️ Failed to update database immediately for {jira_id}")
                    except Exception as e:
                        logger.error(f"❌ Failed to update database for {jira_id}: {e}")
                else:
                    logger.warning(f"⚠️ Database connection not available for immediate update of {jira_id}")
                
                # Add debug logs
                logger.debug(f"🔍 Checking notification conditions: current_status='{current_status}', old_status='{old_status}'")
                
                # Define notification conditions
                verification_variants = ["VERIFICATION", "Verification", "VERIFY", "Verify"]
                done_variants = ["DONE", "Done"]
                # Include "Done" and "DONE" in targets - important for regression/reopened bugs
                old_status_targets = ["NEW", "BACKLOG", "READY", "IN PROGRESS", "DONE", "Done", 
                                     "New", "Backlog", "Ready", "In Progress"]
                verification_targets = ["VERIFICATION", "Verification", "VERIFY", "Verify"]
                
                # 情况1: 状态变更到 VERIFICATION - 每次变更都发送通知
                if current_status in verification_variants and old_status in old_status_targets:
                    logger.info(f"🎯 Trigger immediate VERIFICATION notification: {jira_id} {old_status} -> {current_status}")
                    self._send_immediate_notification({
                        'jiraID': jira_id,
                        'summary': summary,  # Use 'summary' key instead of 'title'
                        'description': description,
                        'old_status': old_status,
                        'status': current_status,
                        'assignee': assignee,
                        'updated': updated,
                        'notification_type': 'status_change',
                        'type': bug.get('type') if bug else None,
                        'testSuite': bug.get('testSuite') if bug else None,
                        'testCase': bug.get('testCase') if bug else None,
                        'testStep': bug.get('testStep') if bug else None,
                        'platform': bug.get('platform') if bug else None,  # Add platform for dynamic URL
                    })
                # 情况2: 从 VERIFICATION 变更到 DONE - 不发送通知，由 MCP callback 处理
                elif current_status in done_variants and old_status in verification_targets:
                    logger.info(f"ℹ️ Status changed {jira_id}: {old_status} -> {current_status} (notification will be sent via MCP callback)")
                else:
                    logger.debug(f"⚠️ Does not meet notification conditions: {jira_id} {old_status} -> {current_status}")
            
            action = "Force check" if force_check else "Cache expired re-check"
            logger.debug(f"🔍 {action} {jira_id}: status={current_status}, assignee={assignee}, priority={priority}")
            return status_info
            
        except Exception as e:
            logger.error(f"❌ Failed to check JIRA {jira_id} status: {e}")
            return None
    
    def get_filtered_bugs_from_jira(self, bugs, is_new_bugs=False):
        """Get bugs with specified status from JIRA, optimized status caching with batch processing
        
        Filtering criteria:
        1. Target statuses: NEW, BACKLOG, READY, IN PROGRESS
        2. Verification status: Always track (notify once on initial detection)
        3. Special case: Done status with Resolved/Accepted resolution
        """
        target_statuses = ["NEW", "BACKLOG", "READY", "IN PROGRESS"]
        immediate_notify_statuses = ["VERIFICATION", "Verification"]
        filtered_bugs = []
        batch_size = 3  # Process 3 bugs per batch
        batch_delay = 5  # 5-second delay between batches
        
        logger.info(f"🔍 Start filtering {'new' if is_new_bugs else 'existing'} bugs' JIRA status...")
        logger.info(f"📊 Target statuses: {target_statuses}")
        logger.info(f"📊 Special case: Done + (Resolved/Accepted)")
        logger.info(f"📊 Immediate notify statuses (for new bugs): {immediate_notify_statuses}")
        logger.info(f"📊 Using batch processing: {batch_size} per batch, {batch_delay} seconds delay between batches")
        
        # Process bugs in batches
        for batch_start in range(0, len(bugs), batch_size):
            batch_end = min(batch_start + batch_size, len(bugs))
            batch_bugs = bugs[batch_start:batch_end]
            batch_num = (batch_start // batch_size) + 1
            total_batches = (len(bugs) + batch_size - 1) // batch_size
            
            logger.info(f"🔄 Processing batch {batch_num}/{total_batches} ({len(batch_bugs)} bugs)")
            
            for bug in batch_bugs:
                jira_id = bug['jiraID']
                
                try:
                    # Force check for new bugs, check cache expiry for existing bugs (auto-decide whether to re-query)
                    jira_status_info = self.check_and_cache_jira_status(jira_id, force_check=is_new_bugs, bug=bug)
                    
                    if jira_status_info:
                        jira_status = jira_status_info['jira_status']
                        resolution = jira_status_info.get('resolution', '')
                        
                        # If status is in target list, add to filtered results
                        if jira_status in target_statuses:
                            bug['jira_status'] = jira_status
                            bug['assignee'] = jira_status_info.get('assignee')
                            bug['updated'] = jira_status_info.get('updated')
                            filtered_bugs.append(bug)
                            logger.debug(f"✅ Filtered bug: {jira_id} - {jira_status}")
                        
                        # Special case: Done status with Resolved/Accepted resolution should be included in tracking
                        elif jira_status.upper() == "DONE" and resolution.upper() in ["RESOLVED", "ACCEPTED"]:
                            bug['jira_status'] = jira_status
                            bug['assignee'] = jira_status_info.get('assignee')
                            bug['updated'] = jira_status_info.get('updated')
                            bug['resolution'] = resolution
                            filtered_bugs.append(bug)
                            logger.info(f"✅ Filtered Done bug with valid resolution: {jira_id} - {jira_status} ({resolution})")
                        
                        # If it's a new bug and status is Verification, send immediate notification (情况D)
                        # But skip if we already sent a status change notification for this bug
                        elif is_new_bugs and jira_status in immediate_notify_statuses:
                            # Initial detection - send notification
                            logger.info(f"🎯 New bug detected with Verification status: {jira_id} - {jira_status}")
                            self._send_immediate_notification({
                                'jiraID': jira_id,
                                'summary': jira_status_info.get('summary') or bug.get('title') or 'No Title Available',
                                'description': jira_status_info.get('description', 'No Description Available'),
                                'status': jira_status,
                                'assignee': jira_status_info.get('assignee', 'Unassigned'),
                                'updated': jira_status_info.get('updated', ''),
                                'notification_type': 'initial_detection',
                                'type': bug.get('type'),
                                'testSuite': bug.get('testSuite'),
                                'testCase': bug.get('testCase'),
                                'testStep': bug.get('testStep'),
                                'platform': bug.get('platform'),  # Add platform for dynamic URL
                            })
                            # Also add to filtered list for tracking
                            bug['jira_status'] = jira_status
                            bug['assignee'] = jira_status_info.get('assignee')
                            bug['updated'] = jira_status_info.get('updated')
                            filtered_bugs.append(bug)
                        
                        # If it's an existing bug with Verification status, continue tracking (no notification)
                        elif not is_new_bugs and jira_status in immediate_notify_statuses:
                            logger.debug(f"🔄 Existing bug with Verification status, continue tracking: {jira_id}")
                            bug['jira_status'] = jira_status
                            bug['assignee'] = jira_status_info.get('assignee')
                            bug['updated'] = jira_status_info.get('updated')
                            filtered_bugs.append(bug)
                        
                        # Debug: Log bugs that don't match any criteria
                        else:
                            logger.debug(f"⚪ Skipped bug (not matching criteria): {jira_id} - Status: {jira_status}, Resolution: {resolution}")
                            logger.debug(f"   Target statuses check: {jira_status in target_statuses}")
                            logger.debug(f"   Done+Resolved check: {jira_status.upper() == 'DONE' and resolution.upper() in ['RESOLVED', 'ACCEPTED']}")
                            if is_new_bugs:
                                logger.debug(f"   Immediate notify check: {jira_status in immediate_notify_statuses}")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to check bug {jira_id} status: {e}")
                    continue
            
            # Delay between batches (except for the last batch)
            if batch_end < len(bugs):
                logger.info(f"⏳ Batch delay {batch_delay} seconds...")
                time.sleep(batch_delay)
        
        logger.info(f"📊 Filtered {len(filtered_bugs)} {'new' if is_new_bugs else 'existing'} bugs that meet criteria")
        return filtered_bugs
    
    def check_for_code_complete(self, filtered_bugs):
        """Check if filtered bugs changed to CODE COMPLETE status, using batch processing"""
        code_complete_bugs = []
        batch_size = 3  # 3 bugs per batch
        batch_delay = 10  # 10-second delay between batches
        
        logger.info(f"🔍 Checking {len(filtered_bugs)} bugs for CODE COMPLETE status...")
        logger.info(f"📊 Using batch processing: {batch_size} per batch, {batch_delay} seconds delay between batches")
        
        # Process in batches
        for batch_start in range(0, len(filtered_bugs), batch_size):
            batch_end = min(batch_start + batch_size, len(filtered_bugs))
            batch_bugs = filtered_bugs[batch_start:batch_end]
            batch_num = (batch_start // batch_size) + 1
            total_batches = (len(filtered_bugs) + batch_size - 1) // batch_size
            
            logger.info(f"🔄 Checking batch {batch_num}/{total_batches} for CODE COMPLETE ({len(batch_bugs)} bugs)")
            
            for bug in batch_bugs:
                jira_id = bug['jiraID']
                old_status = bug.get('jira_status', 'Unknown')
                
                try:
                    # Optimization: if cache has latest status and it's not target status, skip force check
                    cached_info = self.bug_status_cache.get(jira_id)
                    if cached_info:
                        # Use shorter cache (2 minutes) for better status change detection
                        cache_age = (datetime.now() - cached_info['last_check']).total_seconds()
                        cached_status = cached_info.get('jira_status')
                        
                        if cache_age < 30 and cached_status not in ["NEW", "BACKLOG", "READY", "IN PROGRESS", "CODE COMPLETE"]:
                            logger.debug(f"⏭️ Skipping check {jira_id}: status is {cached_status}, not in monitoring range (cached {int(cache_age)}s ago)")
                            continue
                    
                    # Check status (intelligently use cache)
                    jira_status_info = self.check_and_cache_jira_status(jira_id, force_check=False, bug=bug)
                    
                    if jira_status_info:
                        current_status = jira_status_info['jira_status']
                        
                        # Check if changed to CODE COMPLETE
                        if current_status == "CODE COMPLETE":
                            # Check if it's a status change (from target status to CODE COMPLETE)
                            if old_status in ["NEW", "BACKLOG", "READY", "IN PROGRESS"]:
                                code_complete_bugs.append({
                                    'jiraID': jira_id,
                                    'title': bug['title'],
                                    'old_status': old_status,
                                    'new_status': current_status,
                                    'assignee': jira_status_info.get('assignee'),
                                    'updated': jira_status_info.get('updated')
                                })
                                logger.info(f"🎯 Found CODE COMPLETE: {jira_id} {old_status} -> {current_status}")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to check bug {jira_id} for CODE COMPLETE status: {e}")
                    continue
            
            # Delay between batches (except for the last batch)
            if batch_end < len(filtered_bugs):
                logger.info(f"⏳ Batch delay {batch_delay} seconds...")
                time.sleep(batch_delay)
        
        return code_complete_bugs
    
    def send_code_complete_notification(self, code_complete_bugs):
        """Send CODE COMPLETE status notification to Teams"""
        if not code_complete_bugs:
            return
        
        try:
            # Create Adaptive Card for multiple bugs
            card_content = {
                "type": "AdaptiveCard",
                "version": "1.3",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": "🎯 JIRA Bug CODE COMPLETE Notification",
                        "weight": "Bolder",
                        "size": "Medium",
                        "color": "Attention"
                    },
                    {
                        "type": "TextBlock",
                        "text": f"Found {len(code_complete_bugs)} bugs with CODE COMPLETE status",
                        "size": "Small",
                        "color": "Default",
                        "spacing": "Small"
                    }
                ]
            }
            
            # Add each bug as a container
            for bug in code_complete_bugs:
                jira_id = bug['jiraID']
                title = bug.get('title', 'N/A')
                old_status = bug.get('old_status', 'Unknown')
                assignee = bug.get('assignee', 'Unassigned')
                updated = bug.get('updated', '')
                
                bug_container = {
                    "type": "Container",
                    "style": "emphasis",
                    "spacing": "Medium",
                    "items": [
                        {
                            "type": "ColumnSet",
                            "columns": [
                                {
                                    "type": "Column",
                                    "width": "auto",
                                    "items": [
                                        {
                                            "type": "TextBlock",
                                            "text": "✅",
                                            "size": "Large"
                                        }
                                    ]
                                },
                                {
                                    "type": "Column",
                                    "width": "stretch",
                                    "items": [
                                        {
                                            "type": "TextBlock",
                                            "text": f"{jira_id}",
                                            "weight": "Bolder",
                                            "size": "Medium"
                                        },
                                        {
                                            "type": "TextBlock",
                                            "text": f"📝 {title}",
                                            "wrap": True,
                                            "spacing": "Small"
                                        }
                                    ]
                                }
                            ]
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {
                                    "title": "🔄 Status:",
                                    "value": f"{old_status} → CODE COMPLETE"
                                },
                                {
                                    "title": "👤 Assignee:",
                                    "value": assignee
                                },
                                {
                                    "title": "📅 Updated:",
                                    "value": updated
                                }
                            ]
                        },
                        {
                            "type": "ActionSet",
                            "actions": [
                                {
                                    "type": "Action.OpenUrl",
                                    "title": "🔗 View in JIRA",
                                    "url": f"https://jira-eng-gpk2.capx.com/jira/browse/{jira_id}",
                                    "style": "positive"
                                },
                                {
                                    "type": "Action.OpenUrl",
                                    "title": "🔗 Verify this bug",
                                    "url": f"{self.verification_api_url}",
                                    "style": "positive"
                                }
                            ]
                        }
                    ]
                }
                
                card_content["body"].append(bug_container)
            
            # Add timestamp at the end
            card_content["body"].append({
                "type": "TextBlock",
                "text": f"⏰ Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "size": "Small",
                "color": "Default",
                "spacing": "Medium"
            })
            
            # Send to Teams using sendCardToTeams
            self.message_bot.sendCardToTeams(card_content)
            logger.info(f"📨 Sent {len(code_complete_bugs)} CODE COMPLETE notification cards")
            
        except Exception as e:
            logger.error(f"❌ Failed to send CODE COMPLETE notification: {e}")
    
    def send_message_to_mcp_client_async(self, message, jira_id, message_type="bug_status_change", bug_info=None):
        """Send message to MCP client asynchronously with intelligent client selection and queue support
        
        Enhanced version with multi-client pool support and automatic queuing
        
        Args:
            message: Message content (string)
            jira_id: JIRA issue ID for tracking
            message_type: Message type (default: "bug_status_change")
            bug_info: Bug information dictionary (for task assignment)
        """
        def _async_send():
            try:
                logger.info(f"🚀 [ASYNC-{jira_id}] Thread started, attempting to get available client...")
                
                # Extract platform from bug_info for client selection
                platform = None
                if bug_info:
                    platform = bug_info.get('platform')
                    if platform:
                        logger.info(f"🖥️ [ASYNC-{jira_id}] Requesting client for platform: {platform}")
                
                # Try to get an available client from pool (with platform filter if specified)
                client = self.mcp_pool.get_available_client(platform=platform)
                
                if client is None:
                    # No available client, add to queue
                    pool_status = self.mcp_pool.get_pool_status()
                    if platform:
                        logger.warning(f"⏳ [ASYNC-{jira_id}] No available MCP client for platform '{platform}'. Pool status: {pool_status}")
                        logger.warning(f"⚠️ [ASYNC-{jira_id}] Platform '{platform}' may not have configured MCP clients. Task will be queued.")
                    else:
                        logger.warning(f"⏳ [ASYNC-{jira_id}] No available MCP client. Pool status: {pool_status}")
                    logger.info(f"📥 [ASYNC-{jira_id}] Adding to task queue for later processing")
                    
                    # Add task to queue
                    self.mcp_pool.add_to_queue(jira_id, bug_info or {}, message, message_type)
                    return
                
                client_id = client['id']
                client_url = client['url']
                
                logger.info(f"✅ [ASYNC-{jira_id}] Got client: {client_id} ({client['host']}:{client['port']})")
                
                # Assign task to client (changes status from 'reserved' to 'busy')
                if not self.mcp_pool.assign_task(client_id, jira_id, bug_info or {}):
                    logger.error(f"❌ [ASYNC-{jira_id}] Failed to assign task to client {client_id}")
                    self.mcp_pool.unreserve_client(client_id)
                    # Add to queue for retry
                    self.mcp_pool.add_to_queue(jira_id, bug_info or {}, message, message_type)
                    return
                
                # Include callback URL in payload so MCP can notify us when done
                # Include client_id in callback URL for tracking
                callback_url = f"{self.django_callback_url}?client_id={client_id}"
                
                payload = {
                    "command": "execute_workflow",
                    "params": {
                        "message": message,
                        "message_type": message_type,
                        "jira_id": jira_id,
                        "client_id": client_id,  # Include client ID for tracking
                        "callback_url": callback_url  # MCP will POST results here
                    }
                }
                
                logger.info(f"📤 [ASYNC-{jira_id}] Sending request to MCP client {client_id} ({client['host']}) for {jira_id}")
                logger.info(f"🔗 [ASYNC-{jira_id}] Callback URL: {callback_url}")
                logger.debug(f"[ASYNC-{jira_id}] Payload: {payload}")
                
                # Send request with short timeout (just to ensure request is accepted)
                response = requests.post(
                    client_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=10  # Short timeout, just for connection
                )
                
                logger.info(f"📥 [ASYNC-{jira_id}] MCP client {client_id} response: status {response.status_code}")
                
                # Accept both 200 (OK) and 202 (Accepted) as success for async tasks
                if response.status_code not in [200, 202]:
                    logger.warning(f"⚠️ MCP client {client_id} returned error status: {response.status_code}")
                    logger.debug(f"Response: {response.text[:500]}")
                    # Release client on error and process queue
                    released_client = self.mcp_pool.release_client(client_id, jira_id, status='failed')
                    if released_client:
                        self._process_queue_after_release()
                else:
                    logger.info(f"✅ Task successfully dispatched to {client_id} for {jira_id} (status: {response.status_code})")
                    
            except Exception as e:
                logger.error(f"❌ Failed to send async message to MCP client for {jira_id}: {e}")
                # Try to release or unreserve client if it was assigned
                if 'client_id' in locals():
                    # Check if task was assigned (busy) or just reserved
                    with self.mcp_pool.lock:
                        if client_id in self.mcp_pool.active_tasks:
                            # Task was assigned, release it
                            released_client = self.mcp_pool.release_client(client_id, jira_id, status='error')
                            if released_client:
                                self._process_queue_after_release()
                        else:
                            # Task was only reserved, unreserve it
                            self.mcp_pool.unreserve_client(client_id)
                    # Add to queue for retry
                    self.mcp_pool.add_to_queue(jira_id, bug_info or {}, message, message_type)
        
        # Start async thread
        thread = threading.Thread(target=_async_send, daemon=True)
        thread.start()
        logger.info(f"🚀 Async MCP notification thread started for {jira_id}")
    
    def _process_timeout_queue(self):
        """Process queued tasks after timeout cleanup - same as _process_queue_after_release"""
        logger.info(f"🔄 Processing {len(self.mcp_pool.task_queue)} queued tasks after timeout cleanup")
        # Process all available tasks that can be assigned
        while len(self.mcp_pool.task_queue) > 0:
            # Check if any client is available
            with self.mcp_pool.lock:
                available = any(c['status'] == 'idle' for c in self.mcp_pool.clients.values())
            
            if not available:
                logger.debug(f"⏸️ No available clients, {len(self.mcp_pool.task_queue)} tasks remain in queue")
                break
            
            # Process one task
            self._process_queue_after_release()
    
    def _process_queue_after_release(self):
        """Process queued tasks after a client is released"""
        try:
            assigned_tasks = self.mcp_pool.process_queue(max_tasks=1)  # Process one task at a time
            
            for client, task in assigned_tasks:
                # Send the queued task to MCP client
                client_id = client['id']
                client_url = client['url']
                jira_id = task['jira_id']
                message = task['message']
                message_type = task['message_type']
                
                callback_url = f"{self.django_callback_url}?client_id={client_id}"
                
                payload = {
                    "command": "execute_workflow",
                    "params": {
                        "message": message,
                        "message_type": message_type,
                        "jira_id": jira_id,
                        "client_id": client_id,
                        "callback_url": callback_url
                    }
                }
                
                logger.info(f"📤 [QUEUE] Sending queued task to MCP client {client_id} for {jira_id}")
                
                def _send_queued():
                    try:
                        response = requests.post(
                            client_url,
                            json=payload,
                            headers={'Content-Type': 'application/json'},
                            timeout=10
                        )
                        
                        # Accept both 200 (OK) and 202 (Accepted) as success
                        if response.status_code not in [200, 202]:
                            logger.warning(f"⚠️ [QUEUE] MCP client {client_id} returned error status: {response.status_code}")
                            self.mcp_pool.release_client(client_id, jira_id, status='failed')
                        else:
                            logger.info(f"✅ [QUEUE] Queued task successfully dispatched to {client_id} for {jira_id} (status: {response.status_code})")
                    except Exception as e:
                        logger.error(f"❌ [QUEUE] Failed to send queued task to MCP client for {jira_id}: {e}")
                        self.mcp_pool.release_client(client_id, jira_id, status='error')
                
                # Send in background thread
                thread = threading.Thread(target=_send_queued, daemon=True)
                thread.start()
                
        except Exception as e:
            logger.error(f"❌ Failed to process queue after release: {e}")
    
    def send_message_to_mcp_client_async_legacy(self, message, jira_id, message_type="bug_status_change"):
        """Legacy method: Send message to single default MCP client (backward compatibility)
        
        Args:
            message: Message content (string)
            jira_id: JIRA issue ID for tracking
            message_type: Message type (default: "bug_status_change")
        """
        def _async_send():
            try:
                # Include callback URL in payload so MCP can notify us when done
                # Use configured callback URL (with actual server IP, not localhost)
                callback_url = self.django_callback_url
                
                payload = {
                    "command": "execute_workflow",
                    "params": {
                        "message": message,
                        "message_type": message_type,
                        "jira_id": jira_id,
                        "callback_url": callback_url  # MCP will POST results here
                    }
                }
                
                logger.info(f"📤 [LEGACY] Sending async message to default MCP client at {self.mcp_client_url} for {jira_id}")
                logger.info(f"🔗 Callback URL: {callback_url}")
                logger.debug(f"Payload: {payload}")
                
                # Send request with short timeout (just to ensure request is accepted)
                response = requests.post(
                    self.mcp_client_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=10  # Short timeout, just for connection
                )
                
                logger.info(f"📥 MCP client accepted request for {jira_id}: status {response.status_code}")
                
                # Accept both 200 (OK) and 202 (Accepted) as success
                if response.status_code not in [200, 202]:
                    logger.warning(f"⚠️ MCP client returned error status: {response.status_code}")
                    logger.debug(f"Response: {response.text[:500]}")
                    
            except Exception as e:
                logger.error(f"❌ Failed to send async message to MCP client for {jira_id}: {e}")
        
        # Start async thread
        thread = threading.Thread(target=_async_send, daemon=True)
        thread.start()
        logger.info(f"🚀 Async MCP notification started for {jira_id}")
    
    def _send_immediate_code_complete_notification(self, bug_info):
        """Send immediate CODE COMPLETE notification for single bug"""
        try:
            jira_id = bug_info['jiraID']
            title = bug_info.get('title', 'N/A')
            old_status = bug_info.get('old_status', 'Unknown')
            new_status = bug_info.get('new_status', 'CODE COMPLETE')
            assignee = bug_info.get('assignee', 'Unassigned')
            updated = bug_info.get('updated', '')
            
            # Create Adaptive Card for Teams
            card_content = {
                "type": "AdaptiveCard",
                "version": "1.3",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": "🎯 JIRA Bug CODE COMPLETE Notification (Immediate)",
                        "weight": "Bolder",
                        "size": "Medium",
                        "color": "Attention"
                    },
                    {
                        "type": "Container",
                        "style": "emphasis",
                        "items": [
                            {
                                "type": "ColumnSet",
                                "columns": [
                                    {
                                        "type": "Column",
                                        "width": "auto",
                                        "items": [
                                            {
                                                "type": "TextBlock",
                                                "text": "✅",
                                                "size": "Large"
                                            }
                                        ]
                                    },
                                    {
                                        "type": "Column",
                                        "width": "stretch",
                                        "items": [
                                            {
                                                "type": "TextBlock",
                                                "text": f"{jira_id}",
                                                "weight": "Bolder",
                                                "size": "Medium"
                                            },
                                            {
                                                "type": "TextBlock",
                                                "text": f"📝 {title}",
                                                "wrap": True,
                                                "spacing": "Small"
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                "type": "FactSet",
                                "facts": [
                                    {
                                        "title": "🔄 Status:",
                                        "value": f"{old_status} → {new_status}"
                                    },
                                    {
                                        "title": "👤 Assignee:",
                                        "value": assignee
                                    },
                                    {
                                        "title": "📅 Updated:",
                                        "value": updated
                                    },
                                    {
                                        "title": "⏰ Detection Time:",
                                        "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    }
                                ]
                            }
                        ]
                    }
                ],
                "actions": [
                    {
                        "type": "Action.OpenUrl",
                        "title": "🔗 View in JIRA",
                        "url": f"https://jira-eng-gpk2.capx.com/jira/browse/{jira_id}",
                        "style": "positive"
                    },
                    {
                        "type": "Action.OpenUrl",
                        "title": "🔗 Verify this bug",
                        "url": f"{self.verification_api_url}",
                        "style": "positive"
                    }
                ]
            }
            
            # Send to Teams using sendCardToTeams
            self.message_bot.sendCardToTeams(card_content, roomId="653646e0-cf4e-11f0-bf5f-415a52095183")
            logger.info(f"📨 Immediately sent CODE COMPLETE notification card for {jira_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send immediate CODE COMPLETE notification: {e}")
    
    def _send_immediate_notification(self, bug_info):
        """Send immediate notification for bugs with special status (Code Complete, Verification, etc.)"""
        try:
            jira_id = bug_info['jiraID']
            # Properly extract title and description with fallback values
            raw_title = bug_info.get('title') or bug_info.get('summary')
            raw_description = bug_info.get('description')
            
            title = raw_title or 'No Title Available'
            description = raw_description or 'No Description Available'
            
            # Debug logging
            logger.debug(f"🔍 Notification data for {jira_id}:")
            logger.debug(f"  Raw title: {repr(raw_title)}")
            logger.debug(f"  Raw description: {repr(raw_description)}")
            logger.debug(f"  Final title: {repr(title)}")
            logger.debug(f"  Final description: {repr(description[:100])}...")
            
            status = bug_info.get('status', 'Unknown')
            assignee = bug_info.get('assignee', 'Unassigned')
            updated = bug_info.get('updated', '')
            notification_type = bug_info.get('notification_type', 'status_change')
            
            # Extract parameters for dynamic verification URL
            test_suite_for_url = bug_info.get('testSuite', '')
            platform_for_url = bug_info.get('platform', '')
            
            # Debug: Print extracted values
            print(f"🔍 [DEBUG] bug_info keys: {list(bug_info.keys())}")
            print(f"🔍 [DEBUG] test_suite_for_url = '{test_suite_for_url}'")
            print(f"🔍 [DEBUG] platform_for_url = '{platform_for_url}'")
            logger.info(f"🔍 [DEBUG] Extracted for {jira_id}: testSuite='{test_suite_for_url}', platform='{platform_for_url}'")
            
            # Build dynamic verification URL
            verification_url = self.verification_api_url  # Default fallback
            # Check if both values exist and are not 'None' string or 'N/A'
            if (test_suite_for_url and test_suite_for_url not in ['None', 'N/A', ''] and
                platform_for_url and platform_for_url not in ['None', 'N/A', '']):
                # Construct URL with query parameters: suite, platform, vm1
                verification_url = f"https://capx.capx.com/agent_multilingual/?suite={test_suite_for_url}&platform={platform_for_url}&vm1={self.mcp_client_host}"
                logger.info(f"🔗 Dynamic verification URL constructed: {verification_url}")
            else:
                logger.warning(f"⚠️ Invalid testSuite ('{test_suite_for_url}') or platform ('{platform_for_url}') for {jira_id}, using default URL: {verification_url}")
            
            # Create Adaptive Card for Teams
            if notification_type == 'initial_detection':
                card_title = f"🆕 JIRA Bug Initial Detection - {status.upper()}"
                status_info = f"Initial Status: {status}"
                subtitle = f"This bug was detected with {status} status upon first check"
                verification_button_text = "View Verification Progress"
            elif notification_type == 'bug_completion':
                # Bug completion notification (CODE COMPLETE -> DONE)
                old_status = bug_info.get('old_status', 'Unknown')
                card_title = f"✅ Bug Completed - {status.upper()}"
                status_info = f"{old_status} → {status}"
                subtitle = "Bug transitioned from CODE COMPLETE to DONE, development work completed"
                verification_button_text = "View Verification"
            else:
                # Status change notification (e.g., Done -> Verification)
                old_status = bug_info.get('old_status', 'Unknown')
                card_title = f"🔄 JIRA Bug Status Change - {status.upper()}"
                status_info = f"{old_status} → {status}"
                subtitle = "AI Agent has started validating this issue."
                verification_button_text = "View Verification Progress"
            
            card_content = {
                "type": "AdaptiveCard",
                "version": "1.3",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": card_title,
                        "weight": "Bolder",
                        "size": "Medium",
                        "color": "Accent"
                    },
                    {
                        "type": "TextBlock",
                        "text": subtitle,
                        "size": "Small",
                        "color": "Default",
                        "spacing": "Small"
                    },
                    {
                        "type": "Container",
                        "style": "emphasis",
                        "items": [
                            {
                                "type": "ColumnSet",
                                "columns": [
                                    {
                                        "type": "Column",
                                        "width": "auto",
                                        "items": [
                                            {
                                                "type": "TextBlock",
                                                "text": "🎯" if notification_type == 'initial_detection' else ("✅" if notification_type == 'bug_completion' else "✅"),
                                                "size": "Large"
                                            }
                                        ]
                                    },
                                    {
                                        "type": "Column",
                                        "width": "stretch",
                                        "items": [
                                            {
                                                "type": "TextBlock",
                                                "text": f"{jira_id}",
                                                "weight": "Bolder",
                                                "size": "Medium"
                                            },
                                            {
                                                "type": "TextBlock",
                                                "text": f"📝 {title}",
                                                "wrap": True,
                                                "spacing": "Small"
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                "type": "FactSet",
                                "facts": [
                                    {
                                        "title": "🔄 Status:" if notification_type == 'initial_detection' else "🔄 Status:",
                                        "value": status_info
                                    },
                                    {
                                        "title": "👤 Assignee:",
                                        "value": assignee
                                    },
                                    {
                                        "title": "📅 Updated:",
                                        "value": self._format_datetime(updated)
                                    }
                                ]
                            }
                        ]
                    }
                ],
                "actions": [
                    {
                        "type": "Action.OpenUrl",
                        "title": "View in JIRA",
                        "url": f"https://jira-eng-gpk2.capx.com/jira/browse/{jira_id}",
                        "style": "positive"
                    },
                    {
                        "type": "Action.OpenUrl",
                        "title": verification_button_text,
                        "url": verification_url,
                        "style": "positive"
                    }
                ]
            }
            
            # First, send bug information to MCP client
            bug_type = bug_info.get('type', 'Unknown')
            test_suite = bug_info.get('testSuite', 'N/A')
            test_case = bug_info.get('testCase', 'N/A')
            test_step = bug_info.get('testStep', 'N/A')
            
            logger.debug(f"🔍 bug_info keys: {bug_info.keys()}")
            logger.debug(f"🔍 Extracted values - type: {bug_type}, testSuite: {test_suite}, testCase: {test_case}, testStep: {test_step}")
            
            # Check if required test fields are available (not None, not 'N/A', not empty)
            has_valid_test_info = (
                test_suite and test_suite not in ['N/A', 'None'] and
                test_case and test_case not in ['N/A', 'None']
            )
            
            if has_valid_test_info:
                platform = bug_info.get('platform', 'Unknown')
                mcp_message = f"""Bug Status Change Detected:
JIRA ID: {jira_id}
Status: {status}
Type: {bug_type}
Platform: {platform}
test_suite: {test_suite}
test_case: {test_case}
test_step: {test_step}
Title: {title}
Assignee: {assignee}
Updated: {self._format_datetime(updated)}"""
                
                logger.debug(f"📤 MCP message content:\n{mcp_message}")
                
                try:
                    # Step 1: Send Teams card immediately for Verification status
                    logger.info(f"� Step 1: Sending Teams {status} notification card for {jira_id}...")
                    self.message_bot.sendCardToTeams(card_content, roomId="653646e0-cf4e-11f0-bf5f-415a52095183")
                    logger.info(f"✅ Teams card sent successfully for {jira_id}")
                    
                    # Step 2: Send async notification to MCP client (don't wait for result)
                    logger.info(f"📤 Step 2: Sending async notification to MCP client for {jira_id}...")
                    self.send_message_to_mcp_client_async(
                        mcp_message, 
                        jira_id, 
                        message_type="bug_status_change",
                        bug_info=bug_info  # Pass bug_info for task tracking
                    )
                    logger.info(f"✅ MCP notification queued for {jira_id} (will callback when done)")
                        
                except Exception as error:
                    logger.error(f"❌ Failed to send notifications for {jira_id}: {error}")
            else:
                logger.warning(f"⚠️ Skipping MCP client notification for {jira_id}: missing required test info (test_suite={test_suite}, test_case={test_case})")
                logger.info(f"💡 Bug {jira_id} will still be notified via Teams card")
                # If no valid test info, still send Teams card
                self.message_bot.sendCardToTeams(card_content, roomId="653646e0-cf4e-11f0-bf5f-415a52095183")
                logger.info(f"📨 Sent immediate {status} notification card for {jira_id} (type: {notification_type})")
            
        except Exception as e:
            logger.error(f"❌ Failed to send immediate notification: {e}")
    
    def check_all_bugs_status(self):
        """Simplified check logic: get all bugs -> filter specified statuses -> check CODE COMPLETE -> send notifications"""
        logger.info("🔄 Starting simplified JIRA status check...")
        logger.debug(f"📊 Current state: processed_bugs={len(self.processed_bugs)}")
        
        # Check and release timeout tasks before processing new bugs
        timeout_count = self.mcp_pool.check_and_release_timeout_tasks()
        if timeout_count > 0:
            logger.warning(f"⚠️ Released {timeout_count} timeout tasks, freed up clients for new work")
            # Process queued tasks that were waiting
            self._process_timeout_queue()
        
        try:
            # 1. Get new and existing bugs
            new_bugs, existing_bugs = self.get_new_and_existing_bugs()
            if not new_bugs and not existing_bugs:
                logger.info("📝 No bug records found")
                return
            
            # 2. Process new bugs and existing bugs separately
            new_filtered_bugs = []
            existing_filtered_bugs = []
            
            if new_bugs:
                logger.info(f"🆕 Processing {len(new_bugs)} new bugs...")
                new_filtered_bugs = self.get_filtered_bugs_from_jira(new_bugs, is_new_bugs=True)
            
            if existing_bugs:
                logger.info(f"📋 Checking {len(existing_bugs)} existing bugs (using cache)...")
                existing_filtered_bugs = self.get_filtered_bugs_from_jira(existing_bugs, is_new_bugs=False)
            
            # 3. Merge filtered results
            all_filtered_bugs = new_filtered_bugs + existing_filtered_bugs
            
            if not all_filtered_bugs:
                logger.info("🔍 No bugs with specified status found")
                return
            
            # Note: STATUS COMPLETE notifications are already sent immediately in check_and_cache_jira_status method
            # No need to call check_for_code_complete again for duplicate checks and notifications
            logger.info("💡 Status change notifications have been sent immediately during check process")
            
            # 4. Collect all bug updates for database synchronization
            all_bug_updates = []
            all_bugs = new_bugs + existing_bugs
            
            for bug in all_bugs:
                jira_id = bug['jiraID']
                if jira_id in self.bug_status_cache:
                    cached_info = self.bug_status_cache[jira_id]
                    all_bug_updates.append({
                        'jiraID': jira_id,
                        'jira_status': cached_info.get('jira_status', 'Unknown'),
                        'assignee': cached_info.get('assignee', ''),
                        'updated': cached_info.get('updated', ''),
                        'priority': cached_info.get('priority', ''),
                        'resolution': cached_info.get('resolution', '')
                    })
            
            # 5. Synchronize status updates back to database
            if all_bug_updates:
                self.sync_status_to_database(all_bug_updates)
            
            # 6. Process queued tasks if there are any
            pool_status = self.mcp_pool.get_pool_status()
            if pool_status['queued_tasks'] > 0:
                logger.info(f"🔄 Processing task queue ({pool_status['queued_tasks']} tasks pending)...")
                self._process_task_queue()
            
            # 7. Print statistics
            logger.info(f"🎯 Intelligent check completed:")
            logger.info(f"  📊 New bugs: {len(new_bugs) if new_bugs else 0}, filtered: {len(new_filtered_bugs)}")
            logger.info(f"  📊 Existing bugs: {len(existing_bugs) if existing_bugs else 0}, filtered: {len(existing_filtered_bugs)}")
            logger.info(f"  📊 Immediate notifications: sent automatically during status check process")
            logger.info(f"  📊 Cache size: {len(self.bug_status_cache)} statuses")
            logger.info(f"  📊 Database sync: {len(all_bug_updates)} bug statuses updated")
            logger.info(f"  📊 MCP Pool: {pool_status['idle_clients']} idle, {pool_status['busy_clients']} busy, {pool_status['queued_tasks']} queued")
            
        except Exception as e:
            logger.error(f"❌ Intelligent JIRA status check failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _process_task_queue(self):
        """Process queued MCP tasks"""
        try:
            assigned_tasks = self.mcp_pool.process_queue()
            
            for client, task in assigned_tasks:
                # Send the queued task to MCP client
                client_id = client['id']
                client_url = client['url']
                jira_id = task['jira_id']
                message = task['message']
                message_type = task['message_type']
                
                callback_url = f"{self.django_callback_url}?client_id={client_id}"
                
                payload = {
                    "command": "execute_workflow",
                    "params": {
                        "message": message,
                        "message_type": message_type,
                        "jira_id": jira_id,
                        "client_id": client_id,
                        "callback_url": callback_url
                    }
                }
                
                logger.info(f"📤 [QUEUE] Sending queued task to MCP client {client_id} for {jira_id}")
                
                def _send_queued(c_url, p, c_id, j_id):
                    try:
                        response = requests.post(
                            c_url,
                            json=p,
                            headers={'Content-Type': 'application/json'},
                            timeout=10
                        )
                        
                        # Accept both 200 (OK) and 202 (Accepted) as success
                        if response.status_code not in [200, 202]:
                            logger.warning(f"⚠️ [QUEUE] MCP client {c_id} returned error status: {response.status_code}")
                            released = self.mcp_pool.release_client(c_id, j_id, status='failed')
                            if released:
                                self._process_queue_after_release()
                        else:
                            logger.info(f"✅ [QUEUE] Queued task successfully dispatched to {c_id} for {j_id} (status: {response.status_code})")
                    except Exception as e:
                        logger.error(f"❌ [QUEUE] Failed to send queued task to MCP client for {j_id}: {e}")
                        released = self.mcp_pool.release_client(c_id, j_id, status='error')
                        if released:
                            self._process_queue_after_release()
                
                # Send in background thread
                thread = threading.Thread(target=_send_queued, args=(client_url, payload, client_id, jira_id), daemon=True)
                thread.start()
                
        except Exception as e:
            logger.error(f"❌ Failed to process task queue: {e}")
    
    def start_status_check_scheduler(self):
        """Start status check scheduler"""
        try:
            self.scheduler = BackgroundScheduler()
            self.scheduler.add_job(
                self.check_all_bugs_status, 
                'interval', 
                seconds=self.check_interval,
                id='jira_status_checker'
            )
            self.scheduler.start()
            logger.info(f"🔄 JIRA status check scheduler started, check interval: {self.check_interval//60} minutes")
            
        except Exception as e:
            logger.error(f"❌ Failed to start scheduler: {e}")
    
    def stop_scheduler(self):
        """Stop scheduler"""
        self.is_running = False
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("🛑 JIRA status check scheduler stopped")
    
    def clear_cache(self):
        """Clear status cache"""
        self.bug_status_cache.clear()
        self.processed_bugs.clear()
        logger.info("🧹 Status cache cleared")
    
    def sync_status_to_database(self, bug_updates):
        """Synchronize bug status back to database
        
        Args:
            bug_updates: List of dictionaries containing bug status updates
                         Format: [{'jiraID': 'SPARK-123', 'status': 'In Progress', 'assignee': 'John', ...}, ...]
        """
        if not bug_updates or not self.db_connection:
            logger.debug("🔄 No updates to sync or database connection not available")
            return
        
        try:
            update_count = 0
            batch_size = 10  # Process 10 updates per batch
            
            logger.info(f"🔄 Syncing {len(bug_updates)} bug status updates to database...")
            
            for i in range(0, len(bug_updates), batch_size):
                batch = bug_updates[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(bug_updates) + batch_size - 1) // batch_size
                
                logger.debug(f"🔄 Processing sync batch {batch_num}/{total_batches} ({len(batch)} updates)")
                
                for update in batch:
                    jira_id = update.get('jiraID')
                    current_status = update.get('jira_status', 'Unknown')
                    assignee = update.get('assignee', '')
                    updated = update.get('updated', '')
                    
                    if not jira_id:
                        logger.warning("⚠️ Skipping update with missing jiraID")
                        continue
                    
                    try:
                        # Update status in database
                        sql = """
                            UPDATE issue_by_capx
                            SET status = %s
                            WHERE jiraID = %s
                        """
                        
                        success = self.db_connection.ExecuteWithData(sql, (current_status, jira_id))
                        
                        if success:
                            update_count += 1
                            logger.debug(f"✅ Updated {jira_id}: {current_status}")
                        else:
                            logger.warning(f"⚠️ Failed to update {jira_id}")
                            
                    except Exception as e:
                        logger.error(f"❌ Failed to update {jira_id} in database: {e}")
                        continue
                
                # Small delay between batches to avoid overwhelming database
                if i + batch_size < len(bug_updates):
                    time.sleep(0.5)
            
            logger.info(f"✅ Successfully synced {update_count}/{len(bug_updates)} bug status updates to database")
            
        except Exception as e:
            logger.error(f"❌ Failed to sync status to database: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def get_cache_info(self):
        """Get cache information"""
        return {
            'status_cache_size': len(self.bug_status_cache),
            'processed_bugs_count': len(self.processed_bugs),
            'cache_keys': list(self.bug_status_cache.keys())[:5],  # Only show first 5
            'api_call_delay': self.api_call_delay,
            'last_api_call': self.last_api_call
        }
    
    def set_api_delay(self, delay_seconds):
        """Set API call delay (seconds)"""
        self.api_call_delay = max(1, delay_seconds)  # Minimum 1 second
        logger.info(f"🔧 API call delay set to {self.api_call_delay} seconds")
    
    def manual_check(self):
        """Manually trigger status check"""
        logger.info("🔍 Manually triggered status check...")
        self.check_all_bugs_status()

    def force_refresh_bug(self, jira_id):
        """Force refresh a specific bug's status (ignore cache)"""
        logger.info(f"🔄 Force refreshing bug status: {jira_id}")
        try:
            # Force check regardless of cache
            status_info = self.check_and_cache_jira_status(jira_id, force_check=True)
            if status_info:
                current_status = status_info['jira_status']
                logger.info(f"✅ Refreshed {jira_id}: {current_status}")
                return status_info
            else:
                logger.error(f"❌ Failed to refresh {jira_id}")
                return None
        except Exception as e:
            logger.error(f"❌ Exception while refreshing {jira_id}: {e}")
            return None

    def force_refresh_all_bugs(self):
        """Force refresh all bugs in cache"""
        logger.info(f"🔄 Force refreshing all {len(self.bug_status_cache)} cached bugs...")
        refresh_count = 0
        for jira_id in list(self.bug_status_cache.keys()):
            try:
                status_info = self.check_and_cache_jira_status(jira_id, force_check=True)
                if status_info:
                    refresh_count += 1
                time.sleep(1)  # Small delay between refreshes
            except Exception as e:
                logger.error(f"❌ Failed to refresh {jira_id}: {e}")
        logger.info(f"✅ Refreshed {refresh_count} bugs")
    
    def _format_datetime(self, datetime_str):
        """Format datetime string from JIRA API to user-friendly format
        
        Args:
            datetime_str: JIRA datetime string like "2025-09-19T07:29:24.246+0000"
        
        Returns:
            Formatted string like "Sep 19, 2025, 07:29 UTC"
        """
        if not datetime_str:
            return ''
        
        try:
            # Parse the JIRA datetime format
            # Handle both formats: with microseconds and without
            if '.' in datetime_str:
                # Format: 2025-09-19T07:29:24.246+0000
                dt = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%S.%f%z')
            else:
                # Format: 2025-09-19T07:29:24+0000
                dt = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%S%z')
            
            # Convert to UTC and format
            dt_utc = dt.astimezone(timezone.utc) if hasattr(dt, 'astimezone') else dt
            
            # Format as "Sep 19, 2025, 07:29 UTC"
            return dt_utc.strftime('%b %d, %Y, %H:%M UTC')
            
        except (ValueError, AttributeError) as e:
            logger.debug(f"Failed to parse datetime '{datetime_str}': {e}")
            # Return original string if parsing fails
            return datetime_str

# Global instance
jira_status_checker = None

def get_jira_status_checker():
    """Get JIRA status checker instance"""
    global jira_status_checker
    if jira_status_checker is None:
        jira_status_checker = JiraStatusChecker()
    return jira_status_checker

if __name__ == "__main__":
    # Test run
    checker = JiraStatusChecker()
    
    # Manual check once
    checker.manual_check()
    
    # Keep program running
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("🛑 Program interrupted by user")
        checker.stop_scheduler()