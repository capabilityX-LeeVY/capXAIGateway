"""
Session Info API Views
Provides API endpoints for session information management.
"""

import json
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from gpt_gateway.utils.session_tracker import SessionTracker, record_request
from db.session_info_manager import SessionInfoManager


# Initialize session manager
session_manager = SessionInfoManager()


@csrf_exempt
@require_http_methods(["POST"])
def record_session_info(request):
    """
    Record a new session information entry.
    
    POST body:
    - user_id: User identifier (optional)
    - request_method: HTTP method (optional)
    - request_path: Request path (optional)
    - response_status: HTTP response status (optional)
    - response_time_ms: Response time in milliseconds (optional)
    """
    try:
        data = json.loads(request.body) if request.body else {}
        
        # Generate a unique session ID
        import uuid
        session_id = f"api_session_{int(datetime.now().timestamp())}"
        
        # Record the session using the direct manager
        success = session_manager.record_session_request(
            session_id=session_id,
            user_id=data.get('user_id', 'unknown'),
            user_ip=request.META.get('REMOTE_ADDR', '127.0.0.1'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            request_method=data.get('request_method', request.method),
            request_path=data.get('request_path', '/api/session/info/'),
            request_params=data,
            request_headers=dict(request.headers),
            response_status=data.get('response_status', 200),
            response_time_ms=data.get('response_time_ms', 0),
            request_size=len(request.body) if request.body else 0,
            response_size=0  # Will be updated later if needed
        )
        
        if success:
            return JsonResponse({
                'message': 'Session recorded successfully',
                'session_id': session_id
            })
        else:
            return JsonResponse({
                'error': 'Failed to record session in database'
            }, status=500)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'error': f'Failed to record session: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_session_info(request):
    """
    Get session information for a specific session ID.
    
    Query parameters:
    - session_id: Session ID to query
    - limit: Maximum number of records (default: 10)
    """
    with SessionTracker(request) as tracker:
        try:
            session_id = request.GET.get('session_id')
            limit = int(request.GET.get('limit', 10))
            
            if not session_id:
                tracker.set_response_status(400)
                return JsonResponse({
                    'error': 'session_id parameter is required'
                }, status=400)
            
            # Get session records
            sessions = session_manager.get_session_requests(
                session_id=session_id,
                limit=limit
            )
            
            # Convert to JSON-serializable format
            session_data = []
            for session in sessions:
                session_data.append({
                    'id': session[0],
                    'session_id': session[1],
                    'user_id': session[2],
                    'user_ip': session[3],
                    'user_agent': session[4],
                    'request_method': session[5],
                    'request_path': session[6],
                    'request_params': json.loads(session[7]) if session[7] else None,
                    'request_headers': json.loads(session[8]) if session[8] else None,
                    'response_status': session[9],
                    'response_time_ms': session[10],
                    'request_size': session[11],
                    'response_size': session[12],
                    'error_message': session[13],
                    'session_start_time': session[14].isoformat() if session[14] else None,
                    'session_end_time': session[15].isoformat() if session[15] else None,
                    'is_active': bool(session[16]),
                    'created_at': session[17].isoformat() if session[17] else None,
                    'updated_at': session[18].isoformat() if session[18] else None
                })
            
            tracker.set_response_status(200)
            return JsonResponse({
                'session_id': session_id,
                'count': len(session_data),
                'sessions': session_data
            })
            
        except ValueError as e:
            tracker.set_response_status(400)
            tracker.set_error_message(str(e))
            return JsonResponse({
                'error': f'Invalid parameter: {str(e)}'
            }, status=400)
        
        except Exception as e:
            tracker.set_response_status(500)
            tracker.set_error_message(str(e))
            return JsonResponse({
                'error': 'Internal server error'
            }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_recent_sessions(request):
    """
    Get recent session information.
    
    Query parameters:
    - hours: Number of hours to look back (default: 24)
    - limit: Maximum number of records (default: 50)
    """
    with SessionTracker(request) as tracker:
        try:
            hours = int(request.GET.get('hours', 24))
            limit = int(request.GET.get('limit', 50))
            
            # Calculate start time
            start_time = datetime.now() - timedelta(hours=hours)
            
            # Get session records
            sessions = session_manager.get_session_requests(
                start_time=start_time,
                limit=limit
            )
            
            # Convert to JSON-serializable format
            session_data = []
            for session in sessions:
                session_data.append({
                    'id': session[0],
                    'session_id': session[1],
                    'user_id': session[2],
                    'user_ip': session[3],
                    'request_method': session[5],
                    'request_path': session[6],
                    'response_status': session[9],
                    'response_time_ms': session[10],
                    'created_at': session[17].isoformat() if session[17] else None,
                    'is_active': bool(session[16])
                })
            
            tracker.set_response_status(200)
            return JsonResponse({
                'time_range_hours': hours,
                'count': len(session_data),
                'sessions': session_data
            })
            
        except ValueError as e:
            tracker.set_response_status(400)
            tracker.set_error_message(str(e))
            return JsonResponse({
                'error': f'Invalid parameter: {str(e)}'
            }, status=400)
        
        except Exception as e:
            tracker.set_response_status(500)
            tracker.set_error_message(str(e))
            return JsonResponse({
                'error': 'Internal server error'
            }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def end_session(request):
    """
    Mark a session as ended.
    
    POST body:
    - session_id: Session ID to end
    """
    with SessionTracker(request) as tracker:
        try:
            data = json.loads(request.body) if request.body else {}
            session_id = data.get('session_id')
            
            if not session_id:
                tracker.set_response_status(400)
                return JsonResponse({
                    'error': 'session_id is required in request body'
                }, status=400)
            
            # Update session end
            success = session_manager.update_session_end(
                session_id=session_id,
                is_active=False
            )
            
            if success:
                tracker.set_response_status(200)
                return JsonResponse({
                    'message': f'Session {session_id} has been ended',
                    'session_id': session_id
                })
            else:
                tracker.set_response_status(404)
                return JsonResponse({
                    'error': f'No active session found with ID: {session_id}'
                }, status=404)
            
        except json.JSONDecodeError:
            tracker.set_response_status(400)
            tracker.set_error_message('Invalid JSON in request body')
            return JsonResponse({
                'error': 'Invalid JSON in request body'
            }, status=400)
        
        except Exception as e:
            tracker.set_response_status(500)
            tracker.set_error_message(str(e))
            return JsonResponse({
                'error': 'Internal server error'
            }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def session_stats(request):
    """
    Get session statistics.
    """
    with SessionTracker(request) as tracker:
        try:
            # This would require additional queries to get statistics
            # For now, return a simple response
            tracker.set_response_status(200)
            return JsonResponse({
                'message': 'Session statistics endpoint',
                'status': 'active',
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            tracker.set_response_status(500)
            tracker.set_error_message(str(e))
            return JsonResponse({
                'error': 'Internal server error'
            }, status=500)
