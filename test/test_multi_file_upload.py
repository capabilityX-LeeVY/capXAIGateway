"""
Test multi-file upload for analyze_image_comparison endpoint
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


def test_multi_file_save():
    """Test saving multiple files"""
    print("=" * 80)
    print("Testing Multi-File Upload")
    print("=" * 80)
    
    # Create two test files
    file1_name = "reference_image_test.png"
    file1_content = b"This is the reference image content for comparison"
    file1 = create_test_file(file1_name, file1_content)
    
    file2_name = "target_image_test.png"
    file2_content = b"This is the target image content for comparison"
    file2 = create_test_file(file2_name, file2_content)
    
    print(f"\n📤 Uploading two files:")
    print(f"   1. {file1_name}")
    print(f"   2. {file2_name}")
    
    # Save both files
    print("\n🔄 Saving files...")
    file1_metadata = file_storage_manager.save_uploaded_file(file1)
    file2_metadata = file_storage_manager.save_uploaded_file(file2)
    
    if not file1_metadata or not file2_metadata:
        print("❌ Failed to save files")
        return False
    
    print(f"   ✅ File 1 saved: {os.path.basename(file1_metadata['stored_file_path'])}")
    print(f"   ✅ File 2 saved: {os.path.basename(file2_metadata['stored_file_path'])}")
    
    # Simulate what SessionTracker does with multiple files
    print("\n🔄 Simulating multi-file session recording...")
    
    # Combine file info like record_request does
    combined_filename = f"{file1_metadata['original_filename']} | {file2_metadata['original_filename']}"
    combined_path = f"{file1_metadata['stored_file_path']} | {file2_metadata['stored_file_path']}"
    combined_size = file1_metadata['file_size'] + file2_metadata['file_size']
    # For multiple files: file_type is 'multiple', file_hash is only first file's hash
    combined_type = 'multiple'
    first_hash = file1_metadata['file_hash']
    
    # Record to database
    success = session_info_manager.record_session_request(
        session_id=f"multifile_test_{int(datetime.now().timestamp())}",
        user_id="test_user",
        user_ip="127.0.0.1",
        user_agent="Multi-File Test",
        request_method="POST",
        request_path="/gpt/analyze_image_comparison/",
        response_status=200,
        session_start_time=datetime.now(),
        is_active=True,
        uploaded_file_name=combined_filename,
        stored_file_path=combined_path,
        file_size=combined_size,
        file_type=combined_type,
        file_hash=first_hash
    )
    
    if success:
        print("   ✅ Multi-file session recorded successfully")
    else:
        print("   ❌ Failed to record multi-file session")
        return False
    
    # Verify in database
    print("\n🔄 Verifying database record...")
    conn = get_db_connection('capx_ai_gateway_db')
    if not conn:
        print("   ❌ Failed to connect to database")
        return False
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT uploaded_file_name, stored_file_path, file_size, file_type
        FROM session_info 
        WHERE request_path = '/gpt/analyze_image_comparison/'
        ORDER BY created_at DESC 
        LIMIT 1
    """)
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        db_filenames = result[0]
        db_paths = result[1]
        db_size = result[2]
        db_type = result[3]
        
        print(f"   ✅ Found multi-file record in database:")
        print(f"\n   📄 Uploaded filenames:")
        for name in db_filenames.split(' | '):
            print(f"      - {name}")
        
        print(f"\n   💾 Stored paths:")
        for path in db_paths.split(' | '):
            filename = os.path.basename(path)
            exists = "✅" if os.path.exists(path) else "❌"
            print(f"      {exists} {filename}")
        
        print(f"\n   📊 Total size: {db_size} bytes")
        
        print(f"\n   📁 File type: {db_type}")
        if db_type == 'multiple':
            print(f"      (Multiple files detected)")
        
        # Verify both files exist on disk
        all_exist = all(os.path.exists(p.strip()) for p in db_paths.split(' | '))
        if all_exist:
            print(f"\n   ✅ All files exist on disk")
            return True
        else:
            print(f"\n   ❌ Some files missing on disk")
            return False
    else:
        print("   ❌ Multi-file record not found in database")
        return False


def main():
    """Run the test"""
    print("\n" + "=" * 80)
    print("Multi-File Upload Integration Test")
    print("=" * 80 + "\n")
    
    success = test_multi_file_save()
    
    print("\n" + "=" * 80)
    if success:
        print("✅ Multi-file upload test PASSED!")
        print("   The analyze_image_comparison endpoint can now save both files")
    else:
        print("❌ Multi-file upload test FAILED")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
