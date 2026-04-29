from django.urls import path
from . import views
from . import session_views

urlpatterns = [
    path('health_check/', views.health_check_url),
    path('chat/', views.chat),
    path('chat_image/', views.chat_image),
    path('chat_sr/', views.chat_sr),
    path('chat_i18n/', views.chat_i18n),
    path('demo_vision/', views.demo_vision),
    path('analyze_image_comparison/', views.analyze_image_comparison),
    path('analyze_image/', views.analyze_image),
    path('extract_text_from_image/', views.extract_text_from_image),
    path('analyze_performance/', views.analyze_performance),
    
    # Session management endpoints
    path('session/info/', session_views.get_session_info, name='get_session_info'),
    path('session/record/', session_views.record_session_info, name='record_session_info'),
    path('session/recent/', session_views.get_recent_sessions, name='get_recent_sessions'),
    path('session/end/', session_views.end_session, name='end_session'),
    path('session/stats/', session_views.session_stats, name='session_stats'),
]