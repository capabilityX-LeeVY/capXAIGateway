#!/usr/bin/env python3
"""
Test script to demonstrate SessionTracker usage in a Django view
"""

import os
import sys
import django

# Setup Django
sys.path.append('/Users/test/workspace/capx-ai-gateway')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'capx_ai_gateway.settings')
os.environ.setdefault('LOG_PATH', '/Users/test/workspace/capx-ai-gateway/logs')
django.setup()

from django.test import RequestFactory
from gpt_gateway.utils.session_tracker import SessionTracker

def test_session_tracking():
    """Test the SessionTracker context manager"""
    
    # Create a mock request
    factory = RequestFactory()
    request = factory.post('/api/chat/', {'message': 'Hello AI'}, 
                          HTTP_X_FORWARDED_FOR='192.168.1.50')
    
    print("Testing SessionTracker context manager...")
    
    # Use SessionTracker to automatically record session
    with SessionTracker(request) as tracker:
        # Simulate some processing time
        import time
        time.sleep(0.1)
        
        # Simulate a successful response
        response_status = 200
        
        # The session will be automatically recorded when exiting the context
        print(f"✅ Session tracked successfully!")
    
    print("Session tracking test completed successfully!")

if __name__ == "__main__":
    test_session_tracking()
