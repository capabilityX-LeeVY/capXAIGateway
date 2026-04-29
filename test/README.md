# Test Documentation

## Overview

This directory contains comprehensive tests for the WRS AI Gateway project, covering session recording, database connectivity, and API functionality.

## Test Files

### Session Recording Tests
- **`test_session_recording.py`** - Complete session recording system tests
- **`test_session_tracker.py`** - SessionTracker utility tests  
- **`test_session_simple.py`** - Basic session functionality tests

### Database Tests  
- **`test_mysql_session.py`** - MySQL session storage tests
- **`test_connection_simple.py`** - Database connection tests

## Running Tests

### Quick Start
```bash
# Run all tests
python3 test/run_tests.py

# Run specific test category  
python3 test/run_tests.py --session
python3 test/run_tests.py --database

# Verbose output
python3 test/run_tests.py --verbose
```

### Individual Tests
```bash
# Run individual test files
python3 test/test_session_recording.py
python3 test/test_mysql_session.py
python3 test/test_session_tracker.py
```

## Test Requirements

### Environment Setup
```bash
export WRS_ENV=capx-dev
export LOG_PATH=/path/to/logs
export MYSQL_HOST=localhost
export MYSQL_USER=test_user  
export MYSQL_PASSWORD=test_password
export MYSQL_DATABASE=capx_ai_gateway_db
```

### Prerequisites
- MySQL server running
- Database `capx_ai_gateway_db` exists
- Django migrations completed
- Required Python packages installed

## Expected Test Results

### Successful Test Run
```
Running 5 test files...

Running test/test_connection_simple.py...
✅ test/test_connection_simple.py - PASSED

Running test/test_mysql_session.py...
✅ test/test_mysql_session.py - PASSED

Running test/test_session_recording.py...
✅ test/test_session_recording.py - PASSED

Running test/test_session_simple.py...  
✅ test/test_session_simple.py - PASSED

Running test/test_session_tracker.py...
✅ test/test_session_tracker.py - PASSED

==================================================
Test Summary: 5 passed, 0 failed
✅ All tests passed!
```

## Test Coverage

The test suite covers:

- ✅ Database connectivity and table creation
- ✅ Session recording and retrieval 
- ✅ SessionTracker context manager
- ✅ API endpoint session tracking
- ✅ Error handling and edge cases
- ✅ Performance and response time tracking
- ✅ MySQL data persistence
- ✅ Session lifecycle management

## Troubleshooting Tests

### Common Issues

1. **Database Connection Failures**
   ```bash
   # Check MySQL is running
   mysql -u root -p -e "SHOW DATABASES;"
   
   # Verify environment variables
   echo $MYSQL_HOST $MYSQL_USER $MYSQL_DATABASE
   ```

2. **Django Import Errors**
   ```bash
   # Ensure project root is in Python path
   export PYTHONPATH=/Users/test/workspace/capx-ai-gateway:$PYTHONPATH
   
   # Run Django check
   python3 manage.py check
   ```

3. **Session Table Missing**  
   ```bash
   # Run migrations
   python3 manage.py migrate
   
   # Or manually create session table
   mysql -u root -p < db/create_session_info_table.sql
   ```

### Debugging Test Failures

```bash  
# Run with verbose output to see detailed errors
python3 test/run_tests.py --verbose

# Run individual failing test
python3 test/test_session_recording.py

# Check logs
tail -f logs/server.log
```

## Continuous Integration

To integrate with CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Tests
  run: |
    python3 test/run_tests.py
    
- name: Run Session Tests  
  run: |
    python3 test/run_tests.py --session
```

## Adding New Tests

When adding new functionality:

1. Create test file: `test_new_feature.py`
2. Follow existing test patterns
3. Include both success and failure cases
4. Add database cleanup if needed
5. Update this documentation

## Performance Benchmarks

Expected test execution times:
- Database connection tests: < 1 second
- Session recording tests: < 3 seconds
- Full test suite: < 10 seconds

If tests exceed these times, check:
- Database performance
- Network connectivity  
- Resource availability
