#!/usr/bin/env python3
"""
MCP Client Pool Management Script

Usage:
    python mcp_pool_manager.py status          # Show pool status
    python mcp_pool_manager.py clients         # List all clients
    python mcp_pool_manager.py tasks           # Show active tasks
    python mcp_pool_manager.py history         # Show task history
    python mcp_pool_manager.py release <client_id> <jira_id>  # Manually release a client
"""

import sys
import os
import json
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from jira_gateway.jirajob.check_jira_status import get_jira_status_checker


def print_pool_status():
    """Display current pool status"""
    checker = get_jira_status_checker()
    if not checker or not hasattr(checker, 'mcp_pool'):
        print("❌ Error: Could not get JIRA status checker or MCP pool")
        return
    
    pool = checker.mcp_pool  # type: ignore[attr-defined]
    status = pool.get_pool_status()
    
    print("\n" + "="*60)
    print("🏊 MCP CLIENT POOL STATUS")
    print("="*60)
    print(f"📊 Total Clients:  {status['total_clients']}")
    print(f"✅ Idle Clients:   {status['idle_clients']}")
    print(f"🔄 Busy Clients:   {status['busy_clients']}")
    print(f"📋 Active Tasks:   {status['active_tasks']}")
    print(f"⏳ Queued Tasks:   {status['queued_tasks']}")
    print()
    
    print("Client Status:")
    for client_id, client_status in status['clients'].items():
        icon = "✅" if client_status == "idle" else "🔄"
        print(f"  {icon} {client_id}: {client_status}")
    print("="*60 + "\n")


def print_all_clients():
    """List all configured clients with details"""
    checker = get_jira_status_checker()
    if not checker or not hasattr(checker, 'mcp_pool'):
        print("❌ Error: Could not get JIRA status checker or MCP pool")
        return
    
    pool = checker.mcp_pool  # type: ignore[attr-defined]
    
    print("\n" + "="*60)
    print("🖥️  MCP CLIENTS CONFIGURATION")
    print("="*60)
    
    for client_id, client in pool.clients.items():
        print(f"\n📌 {client_id}")
        print(f"   Host:        {client['host']}:{client['port']}")
        print(f"   Description: {client['description']}")
        print(f"   Priority:    {client['priority']}")
        print(f"   Status:      {client['status']}")
        print(f"   Max Tasks:   {client['max_concurrent_tasks']}")
        print(f"   URL:         {client['url']}")
        print(f"   Errors:      {client['error_count']}")
    
    print("="*60 + "\n")


def print_active_tasks():
    """Display currently active tasks"""
    checker = get_jira_status_checker()
    if not checker or not hasattr(checker, 'mcp_pool'):
        print("❌ Error: Could not get JIRA status checker or MCP pool")
        return
    
    pool = checker.mcp_pool  # type: ignore[attr-defined]
    
    print("\n" + "="*60)
    print("🔄 ACTIVE TASKS")
    print("="*60)
    
    if not pool.active_tasks:
        print("✅ No active tasks")
    else:
        for client_id, task in pool.active_tasks.items():
            jira_id = task['jira_id']
            start_time = task['start_time']
            duration = (datetime.now() - start_time).total_seconds()
            
            print(f"\n📋 Task on {client_id}")
            print(f"   JIRA ID:    {jira_id}")
            print(f"   Started:    {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Duration:   {int(duration)} seconds")
            print(f"   Status:     {task['status']}")
    
    print("="*60 + "\n")


def print_task_history():
    """Display task execution history"""
    checker = get_jira_status_checker()
    if not checker or not hasattr(checker, 'mcp_pool'):
        print("❌ Error: Could not get JIRA status checker or MCP pool")
        return
    
    pool = checker.mcp_pool  # type: ignore[attr-defined]
    
    print("\n" + "="*60)
    print("📜 TASK HISTORY (Last 20)")
    print("="*60)
    
    if not pool.task_history:
        print("✅ No task history")
    else:
        # Sort by start time, most recent first
        sorted_tasks = sorted(
            pool.task_history.items(),
            key=lambda x: x[1]['start_time'],
            reverse=True
        )[:20]
        
        for jira_id, task in sorted_tasks:
            client_id = task['client_id']
            status = task['status']
            start_time = task['start_time']
            end_time = task.get('end_time')
            
            status_icon = "✅" if status == "completed" else ("❌" if status == "failed" else "⏳")
            
            duration_str = "running..."
            if end_time:
                duration = (end_time - start_time).total_seconds()
                duration_str = f"{int(duration)}s"
            
            print(f"{status_icon} {jira_id:15} | {client_id:10} | {status:10} | "
                  f"{start_time.strftime('%Y-%m-%d %H:%M:%S')} | {duration_str}")
    
    print("="*60 + "\n")


def manual_release_client(client_id, jira_id):
    """Manually release a client"""
    checker = get_jira_status_checker()
    if not checker or not hasattr(checker, 'mcp_pool'):
        print("❌ Error: Could not get JIRA status checker or MCP pool")
        return
    
    pool = checker.mcp_pool  # type: ignore[attr-defined]
    
    print(f"\n🔓 Attempting to release client {client_id} for task {jira_id}...")
    
    success = pool.release_client(client_id, jira_id, status='manually_released')
    
    if success:
        print(f"✅ Successfully released {client_id}")
    else:
        print(f"❌ Failed to release {client_id}. Client may not be busy with this task.")
    
    print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "status":
        print_pool_status()
    elif command == "clients":
        print_all_clients()
    elif command == "tasks":
        print_active_tasks()
    elif command == "history":
        print_task_history()
    elif command == "release":
        if len(sys.argv) < 4:
            print("❌ Usage: python mcp_pool_manager.py release <client_id> <jira_id>")
            sys.exit(1)
        client_id = sys.argv[2]
        jira_id = sys.argv[3]
        manual_release_client(client_id, jira_id)
    else:
        print(f"❌ Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
