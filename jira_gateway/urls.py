"""
JIRA Gateway URL Configuration
"""

from django.urls import path, re_path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='jira_health_check'),
    path('bug/create/', views.create_bug, name='create_jira_bug'),
    path('task/create/', views.create_task, name='create_jira_task'),
    path('comment/add/', views.add_comment, name='add_jira_comment'),
    path('issues/search/', views.search_issues, name='search_jira_issues'),
    path('statistics/', views.get_statistics, name='jira_statistics'),
    
    # New endpoints for issue details
    path('issue/<str:issue_key>/', views.get_issue_details, name='get_issue_details'),
    path('issue/info/', views.get_issue_basic_info, name='get_issue_basic_info'),
    
    # MCP client callback endpoint (支持带/不带结尾斜杠)
    re_path(r'^mcp_callback/?$', views.mcp_callback, name='mcp_callback'),
]