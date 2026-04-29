"""
Test file naming consistency between database and filesystem
"""
import sys
import os
import io

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from django.core.files.uploadedfile import InMemoryUploadedFile
from gpt_gateway.utils.file_storage_manager import file_storage_manager


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


def test_original_filename_preservation():
    """Test that original filenames are preserved"""
    print("\n" + "=" * 80)
    print("Testing Original Filename Preservation")
    print("=" * 80)
    
    test_cases = [
        ("20260312135834_Privacy Statement opens in a new tab.png", b"test content 1"),
        ("simple_file.jpg", b"test content 2"),
        ("file with spaces.png", b"test content 3"),
        ("中文文件名.jpg", b"test content 4"),
        ("file@#$%special^&chars.png", b"test content 5"),
    ]
    
    results = []
    
    for orig_filename, content in test_cases:
        print(f"\n📄 Testing: {orig_filename}")
        
        # Create test file
        uploaded_file = create_test_file(orig_filename, content)
        
        # Save file
        file_metadata = file_storage_manager.save_uploaded_file(uploaded_file)
        
        if file_metadata:
            stored_path = file_metadata['stored_file_path']
            stored_filename = os.path.basename(stored_path)
            
            print(f"   ✅ Original: {orig_filename}")
            print(f"   ✅ Stored:   {stored_filename}")
            print(f"   📁 Path:     {stored_path}")
            
            # Check if file actually exists
            if os.path.exists(stored_path):
                print(f"   ✅ File exists on disk")
            else:
                print(f"   ❌ File NOT found on disk")
            
            results.append({
                'original': orig_filename,
                'stored': stored_filename,
                'path': stored_path,
                'exists': os.path.exists(stored_path)
            })
        else:
            print(f"   ❌ Failed to save file")
            results.append({
                'original': orig_filename,
                'stored': None,
                'path': None,
                'exists': False
            })
    
    return results


def test_duplicate_handling():
    """Test handling of duplicate filenames with different content"""
    print("\n" + "=" * 80)
    print("Testing Duplicate Filename Handling")
    print("=" * 80)
    
    filename = "test_duplicate.png"
    content1 = b"This is content version 1"
    content2 = b"This is DIFFERENT content version 2"
    
    print(f"\n📄 Testing duplicate filename: {filename}")
    
    # Save first file
    uploaded_file1 = create_test_file(filename, content1)
    metadata1 = file_storage_manager.save_uploaded_file(uploaded_file1)
    
    if metadata1:
        print(f"   ✅ First file saved: {os.path.basename(metadata1['stored_file_path'])}")
    
    # Save second file with same name but different content
    uploaded_file2 = create_test_file(filename, content2)
    metadata2 = file_storage_manager.save_uploaded_file(uploaded_file2)
    
    if metadata2:
        print(f"   ✅ Second file saved: {os.path.basename(metadata2['stored_file_path'])}")
    
    # Check if they are different
    if metadata1 and metadata2:
        if metadata1['stored_file_path'] != metadata2['stored_file_path']:
            print(f"   ✅ Different files stored separately (as expected)")
        else:
            print(f"   ⚠️  Same path used (files might be identical)")
    
    # Save third file with same name AND same content as first
    uploaded_file3 = create_test_file(filename, content1)
    metadata3 = file_storage_manager.save_uploaded_file(uploaded_file3)
    
    if metadata3:
        print(f"   ✅ Third file (duplicate content): {os.path.basename(metadata3['stored_file_path'])}")
        
        if metadata1['stored_file_path'] == metadata3['stored_file_path']:
            print(f"   ✅ Same path reused for identical content (deduplication works)")


def main():
    """Run all tests"""
    print("=" * 80)
    print("File Naming Consistency Test")
    print("=" * 80)
    
    # Test 1: Original filename preservation
    results = test_original_filename_preservation()
    
    # Test 2: Duplicate handling
    test_duplicate_handling()
    
    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    
    success_count = sum(1 for r in results if r['exists'])
    print(f"✅ Successfully saved: {success_count}/{len(results)} files")
    
    print("\n📋 File Mapping:")
    for r in results:
        if r['stored']:
            print(f"  {r['original']}")
            print(f"    → {r['stored']}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
