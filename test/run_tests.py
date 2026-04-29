#!/usr/bin/env python3
"""
Test Runner for WRS AI Gateway

Usage:
    python3 test/run_tests.py                    # Run all tests
    python3 test/run_tests.py --session          # Run session tests only
    python3 test/run_tests.py --database         # Run database tests only
    python3 test/run_tests.py --verbose          # Verbose output
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def run_test_file(test_file, verbose=False):
    """Run a single test file"""
    print(f"Running {test_file}...")
    try:
        cmd = [sys.executable, str(test_file)]
        if verbose:
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                print(f"STDERR:\n{result.stderr}")
            return result.returncode == 0
        else:
            result = subprocess.run(cmd, capture_output=True)
            if result.returncode == 0:
                print(f"✅ {test_file} - PASSED")
            else:
                print(f"❌ {test_file} - FAILED")
            return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running {test_file}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Run WRS AI Gateway tests')
    parser.add_argument('--session', action='store_true', help='Run session tests only')
    parser.add_argument('--database', action='store_true', help='Run database tests only')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    test_dir = Path(__file__).parent
    all_tests = list(test_dir.glob('test_*.py'))
    
    # Filter tests based on arguments
    if args.session:
        tests_to_run = [t for t in all_tests if 'session' in t.name]
    elif args.database:
        tests_to_run = [t for t in all_tests if 'connection' in t.name or 'mysql' in t.name]
    else:
        tests_to_run = all_tests
    
    if not tests_to_run:
        print("No tests found to run!")
        return 1
    
    print(f"Running {len(tests_to_run)} test files...\n")
    
    passed = 0
    failed = 0
    
    for test_file in sorted(tests_to_run):
        if run_test_file(test_file, args.verbose):
            passed += 1
        else:
            failed += 1
        print()
    
    print("=" * 50)
    print(f"Test Summary: {passed} passed, {failed} failed")
    
    if failed > 0:
        print("❌ Some tests failed!")
        return 1
    else:
        print("✅ All tests passed!")
        return 0

if __name__ == '__main__':
    sys.exit(main())
