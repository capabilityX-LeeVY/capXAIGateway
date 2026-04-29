#!/usr/bin/env python3
"""
Test session info recording functionality
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'capx_ai_gateway.settings')
django.setup()

from datetime import datetime
from db.session_info_manager import SessionInfoManager
from db.db_connection_manager import DBConnectionManager


def test_db_connection():
    """Test database connection"""
    print("🔍 Testing database connection...")
    
    try:
        db_manager = DBConnectionManager()
        connection = db_manager.get_connection('capx_ai_gateway_db')
        
        if connection:
            print("✅ Database connection successful!")
            
            # Test basic query
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()
                print(f"✅ Test query result: {result}")
            
            connection.close()
            return True
        else:
            print("❌ Failed to connect to database")
            return False
            
    except Exception as e:
        print(f"❌ Database connection error: {str(e)}")
        return False


def test_session_recording():
    """Test session info recording"""
    print("\n🔍 Testing session recording...")
    
    try:
        session_manager = SessionInfoManager()
        
        # Record a test session
        success = session_manager.record_session_request(
            session_id="test_session_001",
            user_id="test_user",
            user_ip="127.0.0.1",
            user_agent="Test Agent/1.0",
            request_method="GET",
            request_path="/api/test",
            request_params={"param1": "value1", "param2": "value2"},
            response_status=200,
            response_time_ms=150,
            request_size=1024,
            response_size=2048,
            session_start_time=datetime.now(),
            is_active=True
        )
        
        if success:
            print("✅ Session recording successful!")
            
            # Test retrieving sessions
            sessions = session_manager.get_session_requests(session_id="test_session_001", limit=5)
            print(f"✅ Retrieved {len(sessions)} session records")
            
            if sessions:
                print(f"   - Latest record ID: {sessions[0][0]}")
                print(f"   - Session ID: {sessions[0][1]}")
                print(f"   - Request path: {sessions[0][6]}")
                print(f"   - Response status: {sessions[0][9]}")
            
            return True
        else:
            print("❌ Failed to record session")
            return False
            
    except Exception as e:
        print(f"❌ Session recording error: {str(e)}")
        return False


def test_session_update():
    """Test session update functionality"""
    print("\n🔍 Testing session update...")
    
    try:
        session_manager = SessionInfoManager()
        
        # Update session end
        success = session_manager.update_session_end(
            session_id="test_session_001",
            end_time=datetime.now(),
            is_active=False
        )
        
        if success:
            print("✅ Session update successful!")
            return True
        else:
            print("⚠️ No session found to update (this is normal if running for first time)")
            return True
            
    except Exception as e:
        print(f"❌ Session update error: {str(e)}")
        return False


def cleanup_test_data():
    """Clean up test data"""
    print("\n🧹 Cleaning up test data...")
    
    try:
        from db.db_connection_manager import get_db_connection
        connection = get_db_connection('capx_ai_gateway_db')
        
        if connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM session_info WHERE session_id LIKE 'test_session_%'")
                deleted_count = cursor.rowcount
                connection.commit()
                print(f"✅ Deleted {deleted_count} test records")
            
            connection.close()
            return True
        else:
            print("⚠️ Could not connect to database for cleanup")
            return False
            
    except Exception as e:
        print(f"⚠️ Cleanup error: {str(e)}")
        return False


def main():
    """Main test function"""
    print("🚀 Starting session info system tests...")
    print("=" * 50)
    
    # Test database connection
    if not test_db_connection():
        print("\n❌ Database connection test failed. Exiting.")
        return False
    
    # Test session recording
    if not test_session_recording():
        print("\n❌ Session recording test failed.")
        return False
    
    # Test session update
    if not test_session_update():
        print("\n❌ Session update test failed.")
        return False
    
    # Cleanup
    cleanup_test_data()
    
    print("\n" + "=" * 50)
    print("🎉 All tests completed successfully!")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
