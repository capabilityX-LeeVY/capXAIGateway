#!/usr/bin/env python3
"""
Test JIRA Issue Details Functionality

Tests the new get_issue_details functionality with real JIRA issues.
"""

import os
import sys
import requests
import json

# Add project root to Python path
sys.path.append('/Users/test/workspace/capx-ai-gateway')

def test_jira_health_check():
    """Test JIRA connection health"""
    print("🔍 Testing JIRA health check...")
    
    try:
        response = requests.get('http://localhost:9912/jira/health/')
        if response.status_code == 200:
            data = response.json()
            print(f"✅ JIRA Health Check: {data}")
            return data.get('connection_status', False)
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False


def test_get_issue_details_by_path(issue_key="SPARK-702075"):
    """Test getting issue details using path parameter"""
    print(f"\n🔍 Testing issue details by path: {issue_key}")
    
    try:
        url = f'http://localhost:9912/jira/issue/{issue_key}/'
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                issue = data.get('issue', {})
                print("✅ Issue details retrieved successfully!")
                print(f"   Key: {issue.get('key')}")
                print(f"   Summary: {issue.get('summary', '')[:100]}...")
                print(f"   Status: {issue.get('status')}")
                print(f"   Resolution: {issue.get('resolution')}")
                print(f"   Affects Versions: {issue.get('affects_versions')}")
                print(f"   Fix Versions: {issue.get('fix_versions')}")
                print(f"   Comments: {len(issue.get('comments', []))} comments")
                print(f"   URL: {issue.get('url')}")
                return True
            else:
                print(f"❌ API returned success=false")
                return False
        else:
            print(f"❌ Request failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing issue details: {e}")
        return False


def test_get_issue_basic_info(issue_key="SPARK-702075"):
    """Test getting basic issue info using query parameter"""
    print(f"\n🔍 Testing basic issue info: {issue_key}")
    
    try:
        url = f'http://localhost:9912/jira/issue/info/?issue_key={issue_key}'
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                issue_data = data.get('data', {})
                print("✅ Basic issue info retrieved successfully!")
                print(f"   Key: {issue_data.get('key')}")
                print(f"   Summary: {issue_data.get('summary', '')[:100]}...")
                print(f"   Status: {issue_data.get('status')}")
                print(f"   Priority: {issue_data.get('priority')}")
                return True
            else:
                print(f"❌ API returned success=false")
                return False
        else:
            print(f"❌ Request failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing basic issue info: {e}")
        return False


def test_get_filtered_fields(issue_key="SPARK-702075"):
    """Test getting specific fields only"""
    print(f"\n🔍 Testing filtered fields for: {issue_key}")
    
    try:
        fields = "key,summary,status,affects_versions,resolution,comments"
        url = f'http://localhost:9912/jira/issue/info/?issue_key={issue_key}&fields={fields}'
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                issue_data = data.get('data', {})
                print("✅ Filtered fields retrieved successfully!")
                print(f"   Returned fields: {list(issue_data.keys())}")
                for key, value in issue_data.items():
                    if key == 'comments':
                        print(f"   {key}: {len(value) if isinstance(value, list) else value}")
                    elif key == 'summary' and len(str(value)) > 50:
                        print(f"   {key}: {str(value)[:50]}...")
                    else:
                        print(f"   {key}: {value}")
                return True
            else:
                print(f"❌ API returned success=false")
                return False
        else:
            print(f"❌ Request failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing filtered fields: {e}")
        return False


def test_nonexistent_issue():
    """Test handling of nonexistent issue"""
    print(f"\n🔍 Testing nonexistent issue handling...")
    
    try:
        fake_issue = "SPARK-999999999"
        url = f'http://localhost:9912/jira/issue/{fake_issue}/'
        response = requests.get(url)
        
        if response.status_code == 404:
            print("✅ Nonexistent issue handled correctly (404)")
            return True
        elif response.status_code == 200:
            data = response.json()
            if not data.get('success'):
                print("✅ Nonexistent issue handled correctly (success=false)")
                return True
            else:
                print("❌ Expected failure for nonexistent issue")
                return False
        else:
            print(f"⚠️ Unexpected status code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing nonexistent issue: {e}")
        return False


def main():
    """Main test function"""
    print("🚀 Starting JIRA Issue Details Tests...")
    print("=" * 60)
    
    # Test health check first
    if not test_jira_health_check():
        print("\n❌ JIRA health check failed. Please check JIRA connection and configuration.")
        return False
    
    # Test different ways to get issue details
    tests = [
        ("Issue Details by Path", lambda: test_get_issue_details_by_path("SPARK-702075")),
        ("Basic Issue Info", lambda: test_get_issue_basic_info("SPARK-702075")),
        ("Filtered Fields", lambda: test_get_filtered_fields("SPARK-702075")),
        ("Nonexistent Issue", test_nonexistent_issue)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test_name} crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Test Summary: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed!")
        return True
    else:
        print("⚠️ Some tests failed. Please check the output above.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)