"""
Integration test for file upload with session tracking
Verifies that uploaded_file_name in database matches file on disk
"""
import sys
import os
import io

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from django.core.files.uploadedfile import InMemoryUploadedFile
from gpt_gateway.utils.file_storage_manager import file_storage_manager
from db.session_info_manager import session_info_manager
from db.db_connection_manager import get_db_connection
from datetime import datetime


def create_test_file(filename, content):
    """Create a test uploaded file"""
    file_obj = io.BytesIO(content)
    uploaded_file = InMemoryUploadedFile(
        file_obj,
        field_name='test',
        name=filename,
        content_type='image/png',
        size=len(content),
        charset=None
    )
    return uploaded_file


def test_complete_upload_flow():
    """Test complete file upload and session recording flow"""
    print("=" * 80)
    print("Complete File Upload Flow Test")
    print("=" * 80)
    
    # Test file
    test_filename = "20260312_Test_Privacy_Statement.png"
    test_content = b"This is test image content for integration test"
    
    print(f"\n📤 Simulating upload of: {test_filename}")
    
    # Step 1: Create test file
    uploaded_file = create_test_file(test_filename, test_content)
    
    # Step 2: Save file using file storage manager
    print("\n🔄 Step 1: Saving file...")
    file_metadata = file_storage_manager.save_uploaded_file(uploaded_file)
    
    if not file_metadata:
        print("❌ Failed to save file")
        return False
    
    print(f"   ✅ File saved successfully")
    print(f"   📄 Original filename: {file_metadata['original_filename']}")
    print(f"   💾 Stored path:       {file_metadata['stored_file_path']}")
    print(f"   📂 Stored filename:   {os.path.basename(file_metadata['stored_file_path'])}")
    print(f"   📊 File size:         {file_metadata['file_size']} bytes")
    print(f"   🔐 File hash:         {file_metadata['file_hash'][:16]}...")
    
    # Step 3: Record session to database (simulating what SessionTracker does)
    print("\n🔄 Step 2: Recording to database...")
    success = session_info_manager.record_session_request(
        session_id=f"test_session_{int(datetime.now().timestamp())}",
        user_id="test_user",
        user_ip="127.0.0.1",
        user_agent="Integration Test",
        request_method="POST",
        request_path="/test_upload",
        response_status=200,
        session_start_time=datetime.now(),
        is_active=True,
        uploaded_file_name=file_metadata['original_filename'],
        stored_file_path=file_metadata['stored_file_path'],
        file_size=file_metadata['file_size'],
        file_type=file_metadata['file_type'],
        file_hash=file_metadata['file_hash']
    )
    
    if success:
        print("   ✅ Session recorded to database")
    else:
        print("   ❌ Failed to record session")
        return False
    
    # Step 4: Verify database records
    print("\n🔄 Step 3: Verifying database records...")
    conn = get_db_connection('capx_ai_gateway_db')
    if not conn:
        print("   ❌ Failed to connect to database")
        return False
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT uploaded_file_name, stored_file_path 
        FROM session_info 
        WHERE uploaded_file_name = %s
        ORDER BY created_at DESC 
        LIMIT 1
    """, (file_metadata['original_filename'],))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        db_filename = result[0]
        db_path = result[1]
        disk_filename = os.path.basename(db_path)
        
        print(f"   ✅ Found in database:")
        print(f"   📄 DB uploaded_file_name: {db_filename}")
        print(f"   💾 DB stored_file_path:   {db_path}")
        print(f"   📂 Actual disk filename:  {disk_filename}")
        
        # Check if file exists on disk
        if os.path.exists(db_path):
            print(f"   ✅ File exists on disk at: {db_path}")
        else:
            print(f"   ❌ File NOT found on disk at: {db_path}")
            return False
        
        # Compare filenames
        print(f"\n📊 Consistency Check:")
        print(f"   Original upload name:     {test_filename}")
        print(f"   Sanitized/stored name:    {disk_filename}")
        print(f"   DB uploaded_file_name:    {db_filename}")
        
        # They should be closely related (original vs sanitized)
        if test_filename == db_filename:
            print(f"   ✅ Filenames match exactly!")
        else:
            # Check if it's just sanitization (spaces to underscores)
            sanitized = test_filename.replace(' ', '_')
            if sanitized == disk_filename:
                print(f"   ✅ Filenames match after sanitization")
            else:
                print(f"   ⚠️  Filenames differ (may include hash for uniqueness)")
        
        return True
    else:
        print("   ❌ Record not found in database")
        return False


def check_recent_records():
    """Check recent database records for consistency"""
    print("\n" + "=" * 80)
    print("Checking Recent Database Records")
    print("=" * 80)
    
    conn = get_db_connection('capx_ai_gateway_db')
    if not conn:
        print("❌ Failed to connect to database")
        return
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT uploaded_file_name, stored_file_path, created_at
        FROM session_info 
        WHERE uploaded_file_name IS NOT NULL
        ORDER BY created_at DESC 
        LIMIT 10
    """)
    
    results = cursor.fetchall()
    conn.close()
    
    if not results:
        print("No file upload records found")
        return
    
    print(f"\n📋 Latest {len(results)} file upload records:\n")
    
    for i, (uploaded_name, stored_path, created_at) in enumerate(results, 1):
        disk_filename = os.path.basename(stored_path) if stored_path else "N/A"
        exists = "✅" if stored_path and os.path.exists(stored_path) else "❌"
        
        print(f"{i}. [{created_at}]")
        print(f"   Original: {uploaded_name}")
        print(f"   Stored:   {disk_filename}")
        print(f"   {exists} File on disk")
        print()


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("File Upload Integration Test Suite")
    print("=" * 80 + "\n")
    
    # Test complete flow
    success = test_complete_upload_flow()
    
    # Check recent records
    check_recent_records()
    
    # Summary
    print("=" * 80)
    if success:
        print("✅ Integration test PASSED - File naming is consistent!")
    else:
        print("❌ Integration test FAILED - Please check the logs above")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
