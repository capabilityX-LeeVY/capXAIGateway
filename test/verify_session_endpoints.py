"""
Verify that all required endpoints have session tracking enabled
"""
import re

def check_session_tracking():
    """Check which endpoints have SessionTracker enabled"""
    
    views_file = '/Users/test/workspace/capx-ai-gateway/gpt_gateway/views.py'
    
    # Endpoints that should have session tracking
    required_endpoints = {
        '/analyze_image_comparison/': 'analyze_image_comparison',
        '/analyze_image/': 'analyze_image',
        '/chat/': 'chat',
        '/chat_i18n/': 'chat_i18n',
        '/chat_sr/': 'chat_sr',
        '/analyze_performance/': 'analyze_performance'
    }
    
    print("=" * 60)
    print("Session Tracking Verification")
    print("=" * 60)
    
    with open(views_file, 'r') as f:
        content = f.read()
    
    # Find all function definitions and check for SessionTracker
    function_pattern = r'@csrf_exempt\s+def\s+(\w+)\(request\):(.*?)(?=@csrf_exempt|def\s+\w+\(|$)'
    functions = re.findall(function_pattern, content, re.DOTALL)
    
    results = {}
    for func_name, func_body in functions:
        has_session_tracker = 'SessionTracker(request)' in func_body or 'record_request(request' in func_body
        results[func_name] = has_session_tracker
    
    print("\n📊 Required Endpoints Status:\n")
    all_ok = True
    for endpoint, func_name in required_endpoints.items():
        has_tracking = results.get(func_name, False)
        status = "✅ ENABLED" if has_tracking else "❌ MISSING"
        print(f"  {endpoint:35} ({func_name:30}) {status}")
        if not has_tracking:
            all_ok = False
    
    print("\n" + "=" * 60)
    if all_ok:
        print("✅ All required endpoints have session tracking enabled!")
    else:
        print("⚠️  Some endpoints are missing session tracking")
    print("=" * 60)
    
    # Show all functions with tracking for reference
    print("\n📋 All Functions with Session Tracking:\n")
    for func_name, has_tracking in sorted(results.items()):
        if has_tracking:
            print(f"  ✅ {func_name}")
    
    return all_ok

if __name__ == "__main__":
    check_session_tracking()
