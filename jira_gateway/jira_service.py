"""
JIRA Service Module

This module provides high-level JIRA functionality including:
- Creating Issues (Bugs and Tasks)
- Updating JIRA issues
- Managing attachments and comments
- Issue statistics and search

Author: CapabilityX Team
"""

import requests
import json
import mimetypes
from typing import Optional, List, Dict, Any
from datetime import datetime
from jira_gateway.connection_manager import jira_connection_manager
from common.utils.logger import LOGGER_WARNING, LOGGER_INFO, LOGGER_ERROR


class JiraService:
    """
    JIRA Service Class
    
    Provides high-level JIRA operations with proper error handling and logging.
    """
    
    def __init__(self):
        """Initialize JIRA service with connection manager."""
        self.connection_manager = jira_connection_manager
        self.config = self.connection_manager.get_config()
    
    def create_bug(self, 
                   summary: str, 
                   description: str,
                   affects_versions: Optional[List[Dict]] = None,
                   fix_versions: Optional[List[Dict]] = None,
                   assignee: Optional[str] = None,
                   watchers: Optional[List[str]] = None,
                   severity: str = "S3 - Moderate",
                   priority: str = "P3") -> Optional[str]:
        """
        Create a JIRA Bug issue.
        
        Args:
            summary: Issue title
            description: Issue description
            affects_versions: Affected versions
            fix_versions: Fix versions
            assignee: Issue assignee
            watchers: List of watchers
            severity: Bug severity
            priority: Bug priority
            
        Returns:
            Optional[str]: JIRA issue key if successful, None otherwise
        """
        if not self.connection_manager.is_enabled():
            LOGGER_WARNING("JIRA integration is disabled")
            return None
        
        try:
            client = self.connection_manager.get_client()
            if not client:
                return None
            
            # Prepare issue fields
            issue_dict = {
                'project': {'key': self.config.get('default_project', 'SPARK')},
                'summary': summary,
                'description': description,
                'issuetype': {'name': 'Bug'},
                'components': [{"name": "Client: Desktop (Windows and MacOS)"}],
                'labels': ["CapabilityX"],
                'priority': {'name': priority},
                'assignee': {'name': assignee or self.config.get('default_assignee', 'binbiwan')},
                'customfield_10001': self.config.get('default_epic'),  # Epic Link
                'customfield_10712': {"value": "Test"},  # Found
                'customfield_10408': {"value": severity},  # Severity
                'customfield_11800': {"value": self.config.get('default_team', 'Polaris')}  # Team
            }
            
            if affects_versions:
                issue_dict['versions'] = affects_versions
            
            if fix_versions:
                issue_dict['fixVersions'] = fix_versions
            
            # Create issue
            new_issue = client.create_issue(fields=issue_dict)
            jira_id = new_issue.key
            
            LOGGER_INFO(f'New JIRA Bug Created: https://jira-eng-gpk2.capx.com/jira/browse/{jira_id}')
            
            # Add watchers if provided
            if watchers:
                for watcher in watchers:
                    try:
                        client.add_watcher(jira_id, watcher)
                    except Exception as e:
                        LOGGER_ERROR(f"Failed to add watcher {watcher}: {e}")
            
            return jira_id
            
        except Exception as e:
            LOGGER_ERROR(f"Failed to create JIRA bug: {str(e)}")
            return None
    
    def create_task(self,
                    summary: str,
                    description: str,
                    assignee: Optional[str] = None,
                    watchers: Optional[List[str]] = None) -> Optional[str]:
        """
        Create a JIRA Task issue.
        
        Args:
            summary: Issue title
            description: Issue description
            assignee: Issue assignee
            watchers: List of watchers
            
        Returns:
            Optional[str]: JIRA issue key if successful, None otherwise
        """
        if not self.connection_manager.is_enabled():
            LOGGER_WARNING("JIRA integration is disabled")
            return None
        
        try:
            client = self.connection_manager.get_client()
            if not client:
                return None
            
            # Prepare issue fields
            issue_dict = {
                'project': {'key': self.config.get('default_project', 'SPARK')},
                'summary': summary,
                'description': description,
                'issuetype': {'name': 'Task'},
                'components': [{"name": "Client: Desktop (Windows and MacOS)"}],
                'labels': ["CapabilityX"],
                'assignee': {'name': assignee or self.config.get('default_assignee', 'binbiwan')},
                'customfield_10001': self.config.get('default_epic'),  # Epic Link
                'customfield_11800': {"value": self.config.get('default_team', 'Polaris')}  # Team
            }
            
            # Create issue
            new_issue = client.create_issue(fields=issue_dict)
            jira_id = new_issue.key
            
            LOGGER_INFO(f'New JIRA Task Created: https://jira-eng-gpk2.capx.com/jira/browse/{jira_id}')
            
            # Add watchers if provided
            if watchers:
                for watcher in watchers:
                    try:
                        client.add_watcher(jira_id, watcher)
                    except Exception as e:
                        LOGGER_ERROR(f"Failed to add watcher {watcher}: {e}")
            
            return jira_id
            
        except Exception as e:
            LOGGER_ERROR(f"Failed to create JIRA task: {str(e)}")
            return None
    
    def update_issue(self, issue_id: str, fields: Dict[str, Any]) -> bool:
        """
        Update JIRA issue fields.
        
        Args:
            issue_id: JIRA issue ID
            fields: Dictionary of fields to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            client = self.connection_manager.get_client()
            if not client:
                return False
            
            issue = client.issue(issue_id)
            issue.update(fields=fields)
            
            LOGGER_INFO(f'Successfully updated JIRA issue {issue_id}')
            return True
            
        except Exception as e:
            LOGGER_ERROR(f'Failed to update JIRA issue {issue_id}: {e}')
            return False
    
    def add_comment(self, issue_id: str, comment: str) -> bool:
        """
        Add comment to JIRA issue.
        
        Args:
            issue_id: JIRA issue ID
            comment: Comment text
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            client = self.connection_manager.get_client()
            if not client:
                return False
            
            client.add_comment(issue_id, comment)
            LOGGER_INFO(f'Successfully added comment to JIRA issue {issue_id}')
            return True
            
        except Exception as e:
            LOGGER_ERROR(f'Failed to add comment to JIRA issue {issue_id}: {e}')
            return False
    
    def upload_attachments(self, issue_id: str, file_paths: List[str]) -> List[str]:
        """
        Upload attachments to JIRA issue.
        
        Args:
            issue_id: JIRA issue ID
            file_paths: List of file paths to upload
            
        Returns:
            List[str]: List of attachment URLs
        """
        try:
            client = self.connection_manager.get_client()
            if not client:
                return []
            
            attachment_urls = []
            for file_path in file_paths:
                try:
                    with open(file_path, 'rb') as f:
                        attachment = client.add_attachment(issue_id, f, filename=file_path)
                        attachment_urls.append(attachment.content)
                        LOGGER_INFO(f'Successfully uploaded {file_path} to {issue_id}')
                except Exception as e:
                    LOGGER_ERROR(f'Failed to upload {file_path}: {e}')
            
            return attachment_urls
            
        except Exception as e:
            LOGGER_ERROR(f'Failed to upload attachments to {issue_id}: {e}')
            return []
    
    def search_issues(self, jql: str, max_results: int = 1000) -> List[str]:
        """
        Search JIRA issues by JQL query.
        
        Args:
            jql: JQL query string
            max_results: Maximum number of results
            
        Returns:
            List[str]: List of issue keys
        """
        try:
            client = self.connection_manager.get_client()
            if not client:
                return []
            
            issues = client.search_issues(jql, maxResults=max_results)
            return [issue.key for issue in issues]
            
        except Exception as e:
            LOGGER_ERROR(f'Failed to search issues with JQL "{jql}": {e}')
            return []
    
    def get_issue_statistics(self, jql: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get issue statistics by JQL query.
        
        Args:
            jql: JQL query string. If None, defaults to CapabilityX bug filter
            
        Returns:
            Optional[Dict[str, Any]]: Dictionary containing issue statistics
        """
        if jql is None:
            jql = 'labels = CapabilityX and issuetype = Bug'
        
        try:
            client = self.connection_manager.get_client()
            if not client:
                return None
            
            issues = client.search_issues(
                jql, 
                maxResults=1000,
                fields='status,priority,summary,created,updated,issuetype'
            )
            
            total_issues = len(issues)
            status_counts = {}
            priority_counts = {}
            issuetype_counts = {}
            
            for issue in issues:
                status = issue.fields.status.name
                status_counts[status] = status_counts.get(status, 0) + 1
                
                priority = issue.fields.priority.name if issue.fields.priority else "Unset"
                priority_counts[priority] = priority_counts.get(priority, 0) + 1
                
                issuetype = issue.fields.issuetype.name
                issuetype_counts[issuetype] = issuetype_counts.get(issuetype, 0) + 1
            
            result = {
                "total_issues": total_issues,
                "status_breakdown": status_counts,
                "priority_breakdown": priority_counts,
                "issuetype_breakdown": issuetype_counts,
                "jql_query": jql,
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            LOGGER_ERROR(f"Error getting issue statistics: {e}")
            return None
        
    def get_issue_details(self, issue_key: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a JIRA issue.
        
        Args:
            issue_key: JIRA issue key (e.g., 'SPARK-702075')
            
        Returns:
            Optional[Dict[str, Any]]: Issue details or None if not found
        """
        try:
            client = self.connection_manager.get_client()
            if not client:
                return None
            
            # Get issue with expanded fields
            issue = client.issue(
                issue_key,
                expand='changelog,comments,attachments'
            )
            
            # Extract basic information
            issue_details = {
                'key': issue.key,
                'summary': issue.fields.summary,
                'description': issue.fields.description or '',
                'status': issue.fields.status.name if issue.fields.status else None,
                'resolution': issue.fields.resolution.name if issue.fields.resolution else None,
                'priority': issue.fields.priority.name if issue.fields.priority else None,
                'assignee': issue.fields.assignee.displayName if issue.fields.assignee else None,
                'reporter': issue.fields.reporter.displayName if issue.fields.reporter else None,
                'created': issue.fields.created,
                'updated': issue.fields.updated,
                'issue_type': issue.fields.issuetype.name if issue.fields.issuetype else None,
            }
            
            # Extract affects versions
            affects_versions = []
            if hasattr(issue.fields, 'versions') and issue.fields.versions:
                affects_versions = [version.name for version in issue.fields.versions]
            issue_details['affects_versions'] = affects_versions
            
            # Extract fix versions
            fix_versions = []
            if hasattr(issue.fields, 'fixVersions') and issue.fields.fixVersions:
                fix_versions = [version.name for version in issue.fields.fixVersions]
            issue_details['fix_versions'] = fix_versions
            
            # Extract components
            components = []
            if hasattr(issue.fields, 'components') and issue.fields.components:
                components = [component.name for component in issue.fields.components]
            issue_details['components'] = components
            
            # Extract labels
            labels = []
            if hasattr(issue.fields, 'labels') and issue.fields.labels:
                labels = list(issue.fields.labels)
            issue_details['labels'] = labels
            
            # Extract comments
            comments = []
            if hasattr(issue.fields, 'comment') and issue.fields.comment.comments:
                for comment in issue.fields.comment.comments:
                    comments.append({
                        'id': comment.id,
                        'author': comment.author.displayName if comment.author else 'Unknown',
                        'body': comment.body,
                        'created': comment.created,
                        'updated': comment.updated if hasattr(comment, 'updated') else comment.created
                    })
            issue_details['comments'] = comments
            
            # Extract attachments
            attachments = []
            if hasattr(issue.fields, 'attachment') and issue.fields.attachment:
                for attachment in issue.fields.attachment:
                    attachments.append({
                        'id': attachment.id,
                        'filename': attachment.filename,
                        'size': attachment.size,
                        'created': attachment.created,
                        'author': attachment.author.displayName if attachment.author else 'Unknown',
                        'content_url': attachment.content
                    })
            issue_details['attachments'] = attachments
            
            # Extract custom fields (common ones)
            custom_fields = {}
            
            # Epic Link (customfield_10001)
            if hasattr(issue.fields, 'customfield_10001') and issue.fields.customfield_10001:
                custom_fields['epic_link'] = issue.fields.customfield_10001
            
            # Severity (customfield_10408)
            if hasattr(issue.fields, 'customfield_10408') and issue.fields.customfield_10408:
                custom_fields['severity'] = issue.fields.customfield_10408.value if hasattr(issue.fields.customfield_10408, 'value') else str(issue.fields.customfield_10408)
            
            # Team (customfield_11800)
            if hasattr(issue.fields, 'customfield_11800') and issue.fields.customfield_11800:
                custom_fields['team'] = issue.fields.customfield_11800.value if hasattr(issue.fields.customfield_11800, 'value') else str(issue.fields.customfield_11800)
            
            issue_details['custom_fields'] = custom_fields
            
            # Add URL
            issue_details['url'] = f'https://jira-eng-gpk2.capx.com/jira/browse/{issue_key}'
            
            LOGGER_INFO(f'Successfully retrieved details for issue {issue_key}')
            return issue_details
            
        except Exception as e:
            LOGGER_ERROR(f'Failed to get details for issue {issue_key}: {e}')
            return None


# Global service instance
jira_service = JiraService()