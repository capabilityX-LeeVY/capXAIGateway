# AI-ACC-L18N-GATEWAY

Welcome to **AIforBeginners**! This repository is designed to help those new to AI, providing a comprehensive understanding of key AI concepts, hands-on programming exercises, and real-world AI applications.

---

## How to use

### prepare

#### set env

```shell
vi ~/.zprofile
export WRS_ENV=capx-dev

source ~/.zprofile
```

# WRS AI Gateway

A comprehensive AI gateway service that provides intelligent API endpoints for image analysis, text processing, and session management. Built with Django and integrated with OpenAI services for advanced AI capabilities.

## Features

- 🤖 **AI-Powered APIs**: Image analysis, text extraction, and chat completion
- 📊 **Session Recording**: Comprehensive request tracking and analytics
- 🔒 **Secure Integration**: Built-in authentication and error handling
- 📈 **Performance Monitoring**: Response time tracking and system health checks
- 🌐 **Scalable Architecture**: Django-based with MySQL database support

## Quick Start

### Prerequisites

- Python 3.9+
- MySQL 8.0+
- Required environment variables

### Environment Setup

```bash
# Set environment variables
export WRS_ENV=capx-dev
export LOG_PATH=/path/to/logs
export MYSQL_HOST=localhost
export MYSQL_USER=your_user
export MYSQL_PASSWORD=your_password
export MYSQL_DATABASE=capx_ai_gateway_db

# Source the configuration
source ~/.zprofile
```

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd capx-ai-gateway
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Run database migrations**
```bash
python3 manage.py migrate
```

4. **Start the server**
```bash
python3 manage.py runserver 0.0.0.0:9912
```

### Verify Installation

```bash
# Health check
curl http://localhost:9912/api/health_check/

# Chat API test
curl "http://localhost:9912/api/chat/?message=Hello"
```

## API Endpoints

### Core APIs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/gpt/health_check/` | GET | System health status |
| `/gpt/chat/` | GET/POST | AI chat completion |
| `/gpt/analyze_image/` | POST | Image analysis with AI |
| `/gpt/chat_image/` | POST | Image-based chat |
| `/gpt/extract_text_from_image/` | POST | OCR text extraction |

### JIRA Integration APIs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/jira/health/` | GET | JIRA connection health check |
| `/jira/bug/create/` | POST | Create a new JIRA bug |
| `/jira/task/create/` | POST | Create a new JIRA task |
| `/jira/comment/add/` | POST | Add comment to JIRA issue |
| `/jira/issues/search/` | GET | Search JIRA issues by JQL |
| `/jira/issue/<issue_key>/` | GET | Get detailed issue information |
| `/jira/issue/info/` | GET | Get issue info by key parameter |
| `/jira/statistics/` | GET | Get JIRA issue statistics |

### Session Management APIs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/session/record/` | POST | Record a new session |
| `/api/session/recent/` | GET | Get recent sessions |
| `/api/session/info/` | GET | Get session details |
| `/api/session/end/` | POST | End active session |
| `/api/session/stats/` | GET | Session statistics |

### Usage Examples

#### Image Analysis
```bash
curl -X POST "http://localhost:9912/api/analyze_image/" 
  -F "image=@/path/to/image.jpg" 
  -F "message=What do you see in this image?"
```

#### JIRA Integration Examples

```bash
# Check JIRA connection status
curl "http://localhost:9912/jira/health/"

# Get detailed issue information
curl "http://localhost:9912/jira/issue/SPARK-702075/"

# Get specific fields only
curl "http://localhost:9912/jira/issue/info/?issue_key=SPARK-702075&fields=key,summary,status,affects_versions,resolution"

# Create a new bug
curl -X POST "http://localhost:9912/jira/bug/create/" \
  -H "Content-Type: application/json" \
  -d '{
    "summary": "UI display issue in meeting window",
    "description": "The meeting controls overlap in certain screen resolutions",
    "severity": "S3 - Moderate",
    "priority": "P3",
    "affects_versions": [{"name": "WBS41.7.0"}]
  }'

# Search issues by JQL
curl "http://localhost:9912/jira/issues/search/?jql=labels=CapabilityX&max_results=50"

# Add comment to existing issue
curl -X POST "http://localhost:9912/jira/comment/add/" \
  -H "Content-Type: application/json" \
  -d '{
    "issue_id": "SPARK-702075",
    "comment": "Issue has been reproduced and confirmed"
  }'

# Get issue statistics
curl "http://localhost:9912/jira/statistics/"
```

#### Session Recording
```bash
# View recent sessions
curl "http://localhost:9912/api/session/recent/?limit=10"

# Manual session recording
curl -X POST "http://localhost:9912/api/session/record/" 
  -H "Content-Type: application/json" 
  -d '{
    "user_ip": "127.0.0.1",
    "request_path": "/api/test",
    "response_status": 200
  }'
```

## Session Recording System

### Overview

The system automatically records all API requests with detailed metadata including:

- Session ID and user information
- Request method, path, and parameters
- Response status and timing
- IP address and user agent
- Error messages and stack traces

### Database Schema

**Table**: `session_info` (19 fields)
- `session_id`: Unique session identifier
- `user_id`: User identification
- `user_ip`: Client IP address
- `request_method`: HTTP method (GET/POST/etc.)
- `request_path`: API endpoint path
- `response_status`: HTTP status code
- `response_time_ms`: Response time in milliseconds
- `created_at`: Timestamp
- Additional metadata fields...

### Using SessionTracker

```python
from gpt_gateway.utils.session_tracker import SessionTracker

@csrf_exempt
def my_api_view(request):
    with SessionTracker(request) as tracker:
        try:
            # Your business logic here
            result = process_request(request)
            tracker.set_response_status(200)
            return JsonResponse({'result': result})
        except Exception as e:
            tracker.set_response_status(500)
            tracker.set_error_message(str(e))
            return JsonResponse({'error': str(e)}, status=500)
    # Session automatically recorded on exit
```

## Project Structure

```
capx-ai-gateway/
├── db/                          # Database utilities
│   ├── session_info_manager.py  # Session recording manager
│   └── create_session_info_table.sql
├── gpt_gateway/                 # Main Django app
│   ├── views.py                 # API endpoints
│   ├── urls.py                  # URL routing
│   ├── models/                  # OpenAI integration
│   ├── utils/                   # Utility functions
│   │   └── session_tracker.py   # Session tracking utility
│   └── session_views.py         # Session management APIs
├── config/                      # Configuration files
├── test/                        # Test files
├── logs/                        # Log files
└── manage.py                    # Django management
```

## Development

### Running Tests

The project includes a comprehensive test suite in the `/test` directory.

```bash
# Run all tests
python3 test/run_tests.py

# Run specific test categories
python3 test/run_tests.py --session      # Session recording tests
python3 test/run_tests.py --database     # Database connectivity tests
python3 test/run_tests.py --verbose      # Detailed output

# Run individual tests
python3 test/test_session_recording.py
python3 test/test_mysql_session.py
```

**Test Categories:**
- **Session Recording**: Complete session tracking functionality
- **Database Integration**: MySQL connectivity and data persistence  
- **API Functionality**: Endpoint testing and error handling
- **Performance**: Response time and resource usage

### System Health

Check system status:
```bash
python3 manage.py check
```

Monitor logs:
```bash
tail -f logs/server.log
```

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Verify MySQL is running
   - Check environment variables
   - Ensure database exists

2. **Session Recording Not Working**
   - Run Django migrations: `python3 manage.py migrate`
   - Check LOG_PATH environment variable
   - Verify MySQL permissions

3. **OpenAI API Issues**
   - Verify authentication tokens
   - Check network connectivity
   - Monitor rate limits

### Process Management

```bash
# Kill all processes on port 9912
./scripts/killprocess.sh 9912

# Or manually
pkill -f "manage.py runserver"
```

## Performance

- **Session Recording**: < 5ms overhead per request
- **Image Analysis**: 2-8 seconds depending on image size
- **Chat Completion**: 500-2000ms response time
- **Database Queries**: Optimized with connection pooling

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the MIT License.

---

## Kill all processes on the current service port
```shell
./killallprocess.sh portnumber
example ./killallprocess.sh 9901
```

## JIRA Integration

### Configuration

The JIRA integration is configured through `config/jira_config.json`:

```json
{
    "jira": {
        "server": "https://jira-eng-gpk2.capx.com/jira",
        "token": "your_jira_token",
        "default_project": "SPARK",
        "default_epic": "SPARK-559755",
        "default_team": "Polaris",
        "default_assignee": "username",
        "enabled": true
    }
}
```

### Features

- ✅ **Issue Management**: Create bugs and tasks with full metadata
- ✅ **Issue Retrieval**: Get detailed information for any JIRA issue
- ✅ **Field Filtering**: Request only specific fields to reduce payload
- ✅ **Comment Management**: Add comments to existing issues
- ✅ **Search Capabilities**: Use JQL queries to find issues
- ✅ **Statistics**: Get comprehensive issue analytics
- ✅ **Error Handling**: Robust error handling with detailed logging

### Issue Details API

The issue details API provides comprehensive information about JIRA issues:

#### Returned Fields

- `key`: Issue key (e.g., SPARK-702075)
- `summary`: Issue title
- `description`: Full issue description
- `status`: Current status (Open, In Progress, Resolved, etc.)
- `resolution`: Resolution status (Fixed, Won't Fix, etc.)
- `priority`: Issue priority (P1, P2, P3, etc.)
- `affects_versions`: List of affected versions
- `fix_versions`: List of fix versions
- `components`: Associated components
- `labels`: Issue labels
- `comments`: All comments with author and timestamps
- `attachments`: File attachments with metadata
- `custom_fields`: Epic link, severity, team information
- `assignee`: Assigned user
- `reporter`: Issue reporter
- `created`: Creation timestamp
- `updated`: Last update timestamp
- `url`: Direct link to JIRA issue

#### API Examples

```bash
# Get complete issue details
curl "http://localhost:9912/jira/issue/SPARK-702075/"

# Response includes all fields
{
    "success": true,
    "issue": {
        "key": "SPARK-702075",
        "summary": "Issue title here",
        "description": "Detailed description...",
        "status": "Open",
        "resolution": null,
        "affects_versions": ["WBS41.7.0"],
        "fix_versions": ["WBS41.8.0"],
        "comments": [
            {
                "id": "123456",
                "author": "John Doe",
                "body": "Comment text...",
                "created": "2025-08-13T10:30:00.000+0000"
            }
        ],
        "url": "https://jira-eng-gpk2.capx.com/jira/browse/SPARK-702075"
    }
}

# Get only specific fields
curl "http://localhost:9912/jira/issue/info/?issue_key=SPARK-702075&fields=key,summary,status,affects_versions"

# Response with filtered fields
{
    "success": true,
    "issue_key": "SPARK-702075",
    "data": {
        "key": "SPARK-702075",
        "summary": "Issue title here",
        "status": "Open",
        "affects_versions": ["WBS41.7.0"]
    }
}
```

### Programmatic Usage

You can also use JIRA functionality programmatically:

```python
from jira_gateway.jira_service import jira_service

# Get issue details
issue_details = jira_service.get_issue_details("SPARK-702075")
if issue_details:
    print(f"Issue: {issue_details['key']}")
    print(f"Status: {issue_details['status']}")
    print(f"Affects Versions: {issue_details['affects_versions']}")

# Create a bug
jira_id = jira_service.create_bug(
    summary="New bug found",
    description="Detailed description of the bug",
    severity="S3 - Moderate"
)

# Add comment
success = jira_service.add_comment("SPARK-702075", "Investigation completed")
```

### Monitoring JIRA API Usage

All JIRA API calls are automatically tracked in the session recording system. You can monitor:

- API call frequency and patterns
- Response times for JIRA operations
- Error rates and failure patterns
- Most accessed issues

Use Grafana queries like:
```sql
-- JIRA API usage statistics
SELECT 
    request_path,
    COUNT(*) as call_count,
    AVG(response_time_ms) as avg_response_time,
    SUM(CASE WHEN response_status >= 400 THEN 1 ELSE 0 END) as error_count
FROM session_info 
WHERE request_path LIKE '/jira/%'
GROUP BY request_path
ORDER BY call_count DESC;
```

## File Upload & Storage

### File Storage System

The system automatically stores uploaded files with the following features:

- ✅ **Automatic Deduplication**: Uses SHA-256 hash to avoid duplicate storage
- ✅ **Organized Structure**: Files stored in `/uploads/YYYY/MM/DD/` hierarchy  
- ✅ **Metadata Tracking**: All file information recorded in database
- ✅ **Multiple Formats**: Supports images, documents, and other file types

### File Storage Fields

The session_info table includes file-related fields:
- `uploaded_file_name`: Original filename
- `stored_file_path`: Server storage path
- `file_size`: File size in bytes
- `file_type`: MIME type
- `file_hash`: SHA-256 hash for deduplication

### Monitoring File Uploads

```sql
-- File upload statistics in Grafana
SELECT 
    file_type,
    COUNT(*) as upload_count,
    SUM(file_size) as total_size,
    AVG(file_size) as avg_size,
    AVG(response_time_ms) as avg_upload_time
FROM session_info 
WHERE uploaded_file_name IS NOT NULL
GROUP BY file_type
ORDER BY upload_count DESC;
```