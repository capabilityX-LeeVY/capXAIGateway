"""
Test script to verify database connection and session_info table
"""
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from db.db_connection_manager import get_db_connection
from db.session_info_manager import session_info_manager
from datetime import datetime


def test_db_connection():
    """Test database connection"""
    print("\n=== Testing Database Connection ===")
    connection = get_db_connection('capx_ai_gateway_db')
    if connection:
        print("✅ Database connection successful!")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT DATABASE()")
                db_name = cursor.fetchone()[0]
                print(f"✅ Connected to database: {db_name}")
            connection.close()
            return True
        except Exception as e:
            print(f"❌ Error querying database: {e}")
            return False
    else:
        print("❌ Failed to connect to database")
        return False


def test_session_info_table():
    """Test if session_info table exists"""
    print("\n=== Testing session_info Table ===")
    connection = get_db_connection('capx_ai_gateway_db')
    if not connection:
        print("❌ Cannot connect to database")
        return False
    
    try:
        with connection.cursor() as cursor:
            # Check if table exists
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE() 
                AND table_name = 'session_info'
            """)
            table_exists = cursor.fetchone()[0] > 0
            
            if table_exists:
                print("✅ session_info table exists")
                
                # Check table structure
                cursor.execute("DESCRIBE session_info")
                columns = cursor.fetchall()
                print(f"✅ Table has {len(columns)} columns:")
                for col in columns:
                    print(f"   - {col[0]}: {col[1]}")
                
                # Check record count
                cursor.execute("SELECT COUNT(*) FROM session_info")
                count = cursor.fetchone()[0]
                print(f"✅ Table has {count} records")
                
                # Show latest records
                cursor.execute("""
                    SELECT id, session_id, request_method, request_path, 
                           response_status, created_at 
                    FROM session_info 
                    ORDER BY created_at DESC 
                    LIMIT 5
                """)
                latest_records = cursor.fetchall()
                if latest_records:
                    print(f"\n📋 Latest {len(latest_records)} records:")
                    for record in latest_records:
                        print(f"   ID: {record[0]}, Session: {record[1]}, "
                              f"Method: {record[2]}, Path: {record[3]}, "
                              f"Status: {record[4]}, Created: {record[5]}")
                else:
                    print("⚠️  No records in table")
                
                return True
            else:
                print("❌ session_info table does NOT exist")
                print("💡 You may need to create the table using the SQL script")
                return False
                
    except Exception as e:
        print(f"❌ Error checking table: {e}")
        return False
    finally:
        connection.close()


def test_insert_session_record():
    """Test inserting a session record"""
    print("\n=== Testing Session Record Insert ===")
    
    try:
        success = session_info_manager.record_session_request(
            session_id=f"test_session_{int(datetime.now().timestamp())}",
            user_id="test_user",
            user_ip="127.0.0.1",
            user_agent="Test Agent",
            request_method="GET",
            request_path="/test",
            request_params={"test": "data"},
            response_status=200,
            response_time_ms=100,
            session_start_time=datetime.now(),
            is_active=True
        )
        
        if success:
            print("✅ Successfully inserted test session record")
            return True
        else:
            print("❌ Failed to insert test session record")
            return False
            
    except Exception as e:
        print(f"❌ Error inserting session record: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Session Database Diagnostic Tool")
    print("=" * 60)
    
    # Test 1: Database connection
    db_ok = test_db_connection()
    
    # Test 2: Check table
    table_ok = test_session_info_table()
    
    # Test 3: Try to insert a record
    if db_ok and table_ok:
        insert_ok = test_insert_session_record()
        
        # Check the record was inserted
        if insert_ok:
            test_session_info_table()
    
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Database Connection: {'✅ OK' if db_ok else '❌ FAILED'}")
    print(f"  Table Exists: {'✅ OK' if table_ok else '❌ FAILED'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
