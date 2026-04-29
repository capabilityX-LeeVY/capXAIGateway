"""
JIRA Gateway Views
Provides REST API endpoints for JIRA operations.
"""

import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from jira_gateway.jira_service import jira_service
from jira_gateway.connection_manager import jira_connection_manager
from gpt_gateway.utils.session_tracker import SessionTracker
from jira_gateway.jirajob.check_jira_status import get_jira_status_checker


@csrf_exempt
@require_http_methods(["POST"])
def create_bug(request):
    """
    Create a JIRA Bug issue.
    
    POST body:
    {
        "summary": "Bug title",
        "description": "Bug description",
        "affects_versions": [{"name": "WBS41.7.0"}],
        "fix_versions": [{"name": "WBS41.8.0"}],
        "assignee": "username",
        "watchers": ["user1", "user2"],
        "severity": "S3 - Moderate",
        "priority": "P3"
    }
    """
    with SessionTracker(request) as tracker:
        try:
            data = json.loads(request.body) if request.body else {}
            
            # Validate required fields
            if not data.get('summary') or not data.get('description'):
                tracker.set_response_status(400)
                return JsonResponse({
                    'error': 'Summary and description are required'
                }, status=400)
            
            # Create bug
            jira_id = jira_service.create_bug(
                summary=data['summary'],
                description=data['description'],
                affects_versions=data.get('affects_versions'),
                fix_versions=data.get('fix_versions'),
                assignee=data.get('assignee'),
                watchers=data.get('watchers'),
                severity=data.get('severity', 'S3 - Moderate'),
                priority=data.get('priority', 'P3')
            )
            
            if jira_id:
                tracker.set_response_status(201)
                return JsonResponse({
                    'success': True,
                    'jira_id': jira_id,
                    'url': f'https://jira-eng-gpk2.capx.com/jira/browse/{jira_id}'
                }, status=201)
            else:
                tracker.set_response_status(500)
                return JsonResponse({
                    'error': 'Failed to create JIRA bug'
                }, status=500)
            
        except json.JSONDecodeError:
            tracker.set_response_status(400)
            return JsonResponse({
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            tracker.set_response_status(500)
            tracker.set_error_message(str(e))
            return JsonResponse({
                'error': f'Internal server error: {str(e)}'
            }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_task(request):
    """
    Create a JIRA Task issue.
    
    POST body:
    {
        "summary": "Task title",
        "description": "Task description",
        "assignee": "username",
        "watchers": ["user1", "user2"]
    }
    """
    with SessionTracker(request) as tracker:
        try:
            data = json.loads(request.body) if request.body else {}
            
            # Validate required fields
            if not data.get('summary') or not data.get('description'):
                tracker.set_response_status(400)
                return JsonResponse({
                    'error': 'Summary and description are required'
                }, status=400)
            
            # Create task
            jira_id = jira_service.create_task(
                summary=data['summary'],
                description=data['description'],
                assignee=data.get('assignee'),
                watchers=data.get('watchers')
            )
            
            if jira_id:
                tracker.set_response_status(201)
                return JsonResponse({
                    'success': True,
                    'jira_id': jira_id,
                    'url': f'https://jira-eng-gpk2.capx.com/jira/browse/{jira_id}'
                }, status=201)
            else:
                tracker.set_response_status(500)
                return JsonResponse({
                    'error': 'Failed to create JIRA task'
                }, status=500)
            
        except json.JSONDecodeError:
            tracker.set_response_status(400)
            return JsonResponse({
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            tracker.set_response_status(500)
            tracker.set_error_message(str(e))
            return JsonResponse({
                'error': f'Internal server error: {str(e)}'
            }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def add_comment(request):
    """
    Add comment to JIRA issue.
    
    POST body:
    {
        "issue_id": "SPARK-12345",
        "comment": "This is a comment"
    }
    """
    with SessionTracker(request) as tracker:
        try:
            data = json.loads(request.body) if request.body else {}
            
            issue_id = data.get('issue_id')
            comment = data.get('comment')
            
            if not issue_id or not comment:
                tracker.set_response_status(400)
                return JsonResponse({
                    'error': 'issue_id and comment are required'
                }, status=400)
            
            success = jira_service.add_comment(issue_id, comment)
            
            if success:
                tracker.set_response_status(200)
                return JsonResponse({
                    'success': True,
                    'message': f'Comment added to {issue_id}'
                })
            else:
                tracker.set_response_status(500)
                return JsonResponse({
                    'error': 'Failed to add comment'
                }, status=500)
            
        except json.JSONDecodeError:
            tracker.set_response_status(400)
            return JsonResponse({
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            tracker.set_response_status(500)
            tracker.set_error_message(str(e))
            return JsonResponse({
                'error': f'Internal server error: {str(e)}'
            }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def search_issues(request):
    """
    Search JIRA issues by JQL query.
    
    Query parameters:
    - jql: JQL query string
    - max_results: Maximum number of results (default: 100)
    """
    with SessionTracker(request) as tracker:
        try:
            jql = request.GET.get('jql')
            max_results = int(request.GET.get('max_results', 100))
            
            if not jql:
                tracker.set_response_status(400)
                return JsonResponse({
                    'error': 'jql parameter is required'
                }, status=400)
            
            issue_keys = jira_service.search_issues(jql, max_results)
            
            tracker.set_response_status(200)
            return JsonResponse({
                'success': True,
                'issues': issue_keys,
                'count': len(issue_keys),
                'jql': jql
            })
            
        except ValueError:
            tracker.set_response_status(400)
            return JsonResponse({
                'error': 'max_results must be a valid integer'
            }, status=400)
        except Exception as e:
            tracker.set_response_status(500)
            tracker.set_error_message(str(e))
            return JsonResponse({
                'error': f'Internal server error: {str(e)}'
            }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_statistics(request):
    """
    Get JIRA issue statistics.
    
    Query parameters:
    - jql: JQL query string (optional, defaults to CapabilityX bugs)
    """
    with SessionTracker(request) as tracker:
        try:
            jql = request.GET.get('jql')
            
            statistics = jira_service.get_issue_statistics(jql)
            
            if statistics:
                tracker.set_response_status(200)
                return JsonResponse({
                    'success': True,
                    'statistics': statistics
                })
            else:
                tracker.set_response_status(500)
                return JsonResponse({
                    'error': 'Failed to get statistics'
                }, status=500)
            
        except Exception as e:
            tracker.set_response_status(500)
            tracker.set_error_message(str(e))
            return JsonResponse({
                'error': f'Internal server error: {str(e)}'
            }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """Test JIRA connection and configuration."""
    with SessionTracker(request) as tracker:
        try:
            connection_status = jira_connection_manager.test_connection()
            config = jira_connection_manager.get_config()
            
            tracker.set_response_status(200)
            return JsonResponse({
                'success': True,
                'connection_status': connection_status,
                'enabled': jira_connection_manager.is_enabled(),
                'server': config.get('server'),
                'project': config.get('default_project')
            })
            
        except Exception as e:
            tracker.set_response_status(500)
            tracker.set_error_message(str(e))
            return JsonResponse({
                'error': f'Health check failed: {str(e)}'
            }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_issue_details(request, issue_key):
    """
    Get detailed information for a JIRA issue.
    
    URL: /jira/issue/<issue_key>/
    Example: /jira/issue/SPARK-702075/
    """
    with SessionTracker(request) as tracker:
        try:
            if not issue_key:
                tracker.set_response_status(400)
                return JsonResponse({
                    'error': 'Issue key is required'
                }, status=400)
            
            issue_details = jira_service.get_issue_details(issue_key)
            
            if issue_details:
                tracker.set_response_status(200)
                return JsonResponse({
                    'success': True,
                    'issue': issue_details
                })
            else:
                tracker.set_response_status(404)
                return JsonResponse({
                    'error': f'Issue {issue_key} not found or access denied'
                }, status=404)
            
        except Exception as e:
            tracker.set_response_status(500)
            tracker.set_error_message(str(e))
            return JsonResponse({
                'error': f'Internal server error: {str(e)}'
            }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_issue_basic_info(request):
    """
    Get basic information for a JIRA issue by issue key parameter.
    
    Query parameters:
    - issue_key: JIRA issue key (e.g., SPARK-702075)
    - fields: Comma-separated list of fields to include (optional)
    
    Example: /jira/issue/info/?issue_key=SPARK-702075&fields=key,summary,status,affects_versions
    """
    with SessionTracker(request) as tracker:
        try:
            issue_key = request.GET.get('issue_key')
            requested_fields = request.GET.get('fields', '').split(',') if request.GET.get('fields') else None
            
            if not issue_key:
                tracker.set_response_status(400)
                return JsonResponse({
                    'error': 'issue_key parameter is required'
                }, status=400)
            
            issue_details = jira_service.get_issue_details(issue_key)
            
            if issue_details:
                # Filter fields if requested
                if requested_fields:
                    filtered_details = {}
                    for field in requested_fields:
                        field = field.strip()
                        if field in issue_details:
                            filtered_details[field] = issue_details[field]
                    issue_details = filtered_details
                
                tracker.set_response_status(200)
                return JsonResponse({
                    'success': True,
                    'issue_key': issue_key,
                    'data': issue_details
                })
            else:
                tracker.set_response_status(404)
                return JsonResponse({
                    'error': f'Issue {issue_key} not found or access denied'
                }, status=404)
            
        except Exception as e:
            tracker.set_response_status(500)
            tracker.set_error_message(str(e))
            return JsonResponse({
                'error': f'Internal server error: {str(e)}'
            }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def mcp_callback(request):
    """
    MCP client callback endpoint - receives test execution results
    Enhanced with multi-client pool support
    
    POST body from MCP client:
    {
        "jira_id": "SPARK-12345",
        "client_id": "mcp-1",  // Optional: which client processed this task
        "success": true,
        "verification": true,
        "message": "Test execution completed",
        "error": null  // or error message if failed
    }
    
    Query params:
        client_id: Client ID (alternative way to pass client_id)
    """
    with SessionTracker(request) as tracker:
        try:
            # Debug: print raw request body
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"🔍 MCP callback received, raw body: {request.body}")
            
            data = json.loads(request.body) if request.body else {}
            
            jira_id = data.get('jira_id')
            success = data.get('success', False)
            verification = data.get('verification', False)
            message = data.get('message', '')
            error = data.get('error')
            
            # Get client_id from either POST body or query params
            client_id = data.get('client_id') or request.GET.get('client_id')
            
            if not jira_id:
                logger.warning(f"⚠️ MCP callback missing jira_id, data: {data}")
                tracker.set_response_status(400)
                return JsonResponse({
                    'error': 'jira_id is required'
                }, status=400)
            
            # Log the callback
            logger.info(f"📥 MCP callback received for {jira_id}: success={success}, verification={verification}, client_id={client_id}")
            logger.debug(f"Callback data: {data}")
            
            # Release the client from pool if client_id is provided
            if client_id:
                try:
                    checker = get_jira_status_checker()
                    if checker and hasattr(checker, 'mcp_pool'):
                        release_status = 'completed' if (success and verification) else 'failed'
                        released_client = checker.mcp_pool.release_client(client_id, jira_id, status=release_status)
                        logger.info(f"🔓 Released MCP client {client_id} for {jira_id} with status: {release_status}")
                        
                        # Process queued tasks if client was released and queue is not empty
                        if released_client and hasattr(checker, '_process_queue_after_release'):
                            logger.info(f"🔄 Checking queue after callback release...")
                            checker._process_queue_after_release()
                        
                        # Log pool status after release
                        pool_status = checker.mcp_pool.get_pool_status()
                        logger.info(f"📊 Pool status after release: {pool_status}")
                except Exception as e:
                    logger.error(f"❌ Failed to release client {client_id}: {e}")
            else:
                logger.debug(f"ℹ️ No client_id provided in callback for {jira_id}")
            
            # Send notification card for both success and failure cases
            if success:
                # MCP test execution succeeded - send card regardless of verification result
                card_title = "✅ JIRA Bug - Test Execution Completed" if verification else "❌ JIRA Bug - Verification Failed"
                card_color = "Good" if verification else "Attention"
                emoji = "✅" if verification else "❌"
                result_text = "✅ Passed" if verification else "❌ Failed"
                
                logger.info(f"{'✅' if verification else '❌'} MCP client test completed for {jira_id} (verification={verification}), sending card...")
                
                try:
                    # Get JIRA status checker instance
                    checker = get_jira_status_checker()
                    
                    # Query current bug info from JIRA
                    bug_details = jira_service.get_issue_details(jira_id)
                    
                    if not bug_details:
                        logger.warning(f"⚠️ Could not fetch JIRA details for {jira_id}")
                        tracker.set_response_status(200)  # Still return success to MCP
                        return JsonResponse({
                            'success': True,
                            'message': 'Callback received but could not fetch JIRA details'
                        })
                    
                    # Create status card
                    status_field = bug_details.get('status', {})
                    current_status = status_field.get('name', 'Unknown') if isinstance(status_field, dict) else str(status_field)
                    
                    assignee_field = bug_details.get('assignee', {})
                    assignee = assignee_field.get('displayName', 'Unassigned') if isinstance(assignee_field, dict) else str(assignee_field)
                    
                    updated = bug_details.get('updated', '')
                    title = bug_details.get('summary', 'N/A')
                    
                    # Get report_url from callback data if available
                    report_url = data.get('report_url', '')
                    
                    card_content = {
                        "type": "AdaptiveCard",
                        "version": "1.3",
                        "body": [
                            {
                                "type": "TextBlock",
                                "text": card_title,
                                "weight": "Bolder",
                                "size": "Medium",
                                "color": card_color
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
                                                        "text": emoji,
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
                                                "value": current_status
                                            },
                                            {
                                                "title": "👤 Assignee:",
                                                "value": assignee
                                            },
                                            {
                                                "title": "📅 Test Completed:",
                                                "value": checker._format_datetime(updated) if hasattr(checker, '_format_datetime') else updated
                                            },
                                            {
                                                "title": "🎯 Test Result:",
                                                "value": result_text
                                            }
                                        ] + ([{"title": "🖥️ Verified by:", "value": client_id}] if client_id else [])
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": f"💬 {message}" if message else "Test execution completed",
                                        "wrap": True,
                                        "spacing": "Small",
                                        "color": card_color
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
                            }
                        ] + ([{
                            "type": "Action.OpenUrl",
                            "title": "View Report",
                            "url": report_url,
                            "style": "default"
                        }] if report_url else [])
                    }
                    
                    # Send card to Teams
                    from jira_gateway.tojirabug import MessageBot
                    message_bot = MessageBot()
                    message_bot.sendCardToTeams(card_content, roomId="653646e0-cf4e-11f0-bf5f-415a52095183")
                    
                    logger.info(f"📨 Test result card sent to Teams for {jira_id} (verification={verification})")
                    
                    tracker.set_response_status(200)
                    return JsonResponse({
                        'success': True,
                        'message': f'Card sent for {jira_id}'
                    })
                    
                except Exception as send_error:
                    logger.error(f"❌ Failed to send card for {jira_id}: {send_error}")
                    tracker.set_response_status(200)  # Still return success to MCP
                    return JsonResponse({
                        'success': True,
                        'message': 'Callback received but failed to send card',
                        'error': str(send_error)
                    })
            else:
                # MCP test execution failed
                logger.warning(f"⚠️ MCP client reported execution failure for {jira_id}: {error}")
                
                tracker.set_response_status(200)
                return JsonResponse({
                    'success': True,
                    'message': f'Callback received for {jira_id} (test execution failed)'
                })
            
        except json.JSONDecodeError:
            tracker.set_response_status(400)
            return JsonResponse({
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            tracker.set_response_status(500)
            tracker.set_error_message(str(e))
            return JsonResponse({
                'error': f'Callback processing failed: {str(e)}'
            }, status=500)
