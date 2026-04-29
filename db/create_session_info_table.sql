-- Create session_info table for recording session access request information
-- Database: capx_ai_gateway_db

USE capx_ai_gateway_db;

-- Drop table if exists
DROP TABLE IF EXISTS session_info;

-- Create session_info table
CREATE TABLE session_info (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Primary key ID',
    session_id VARCHAR(255) NOT NULL COMMENT 'Session ID',
    user_id VARCHAR(100) DEFAULT NULL COMMENT 'User ID',
    user_ip VARCHAR(45) DEFAULT NULL COMMENT 'User IP address',
    user_agent TEXT DEFAULT NULL COMMENT 'User agent string',
    request_method VARCHAR(10) NOT NULL COMMENT 'Request method (GET/POST/PUT/DELETE etc)',
    request_path VARCHAR(500) NOT NULL COMMENT 'Request path',
    request_params TEXT DEFAULT NULL COMMENT 'Request parameters (JSON format)',
    request_headers TEXT DEFAULT NULL COMMENT 'Request headers (JSON format)',
    response_status INT DEFAULT NULL COMMENT 'HTTP response status code',
    response_time_ms INT DEFAULT NULL COMMENT 'Response time in milliseconds',
    request_size INT DEFAULT NULL COMMENT 'Request size in bytes',
    response_size INT DEFAULT NULL COMMENT 'Response size in bytes',
    error_message TEXT DEFAULT NULL COMMENT 'Error message',
    session_start_time DATETIME DEFAULT NULL COMMENT 'Session start time',
    session_end_time DATETIME DEFAULT NULL COMMENT 'Session end time',
    is_active TINYINT(1) DEFAULT 1 COMMENT 'Whether session is active (1:active, 0:inactive)',
    -- New fields for file storage
    uploaded_file_name VARCHAR(500) DEFAULT NULL COMMENT 'Original uploaded file name',
    stored_file_path VARCHAR(1000) DEFAULT NULL COMMENT 'Stored file path on server',
    file_size BIGINT DEFAULT NULL COMMENT 'File size in bytes',
    file_type VARCHAR(100) DEFAULT NULL COMMENT 'File MIME type',
    file_hash VARCHAR(64) DEFAULT NULL COMMENT 'File SHA-256 hash for deduplication',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Session access request records table';

-- Create indexes with proper key length limits
CREATE INDEX idx_session_id ON session_info (session_id);
CREATE INDEX idx_user_id ON session_info (user_id);
CREATE INDEX idx_user_ip ON session_info (user_ip);
CREATE INDEX idx_request_path ON session_info (request_path(191)); -- Limit to 191 chars for utf8mb4
CREATE INDEX idx_response_status ON session_info (response_status);
CREATE INDEX idx_created_at ON session_info (created_at);
CREATE INDEX idx_session_created ON session_info (session_id, created_at);
CREATE INDEX idx_user_ip_created ON session_info (user_ip, created_at);
CREATE INDEX idx_active_sessions ON session_info (is_active, session_start_time);
CREATE INDEX idx_session_time_range ON session_info (session_id, session_start_time, session_end_time);
CREATE INDEX idx_status_time ON session_info (response_status, created_at);

-- Add new indexes for file-related queries with proper length limits
CREATE INDEX idx_file_hash ON session_info (file_hash);
CREATE INDEX idx_file_type ON session_info (file_type);
CREATE INDEX idx_stored_file_path ON session_info (stored_file_path(191)); -- Limit to 191 chars for utf8mb4
CREATE INDEX idx_uploaded_file_name ON session_info (uploaded_file_name(191)); -- Limit to 191 chars for utf8mb4

-- Create partitions (optional, suitable for large data scenarios)
-- Partition by month, can be adjusted as needed
-- ALTER TABLE session_info PARTITION BY RANGE (YEAR(created_at) * 100 + MONTH(created_at)) (
--     PARTITION p202508 VALUES LESS THAN (202509),
--     PARTITION p202509 VALUES LESS THAN (202510),
--     PARTITION p202510 VALUES LESS THAN (202511),
--     PARTITION p202511 VALUES LESS THAN (202512),
--     PARTITION p202512 VALUES LESS THAN (202601),
--     PARTITION p_future VALUES LESS THAN MAXVALUE
-- );

-- Verify table structure
DESCRIBE session_info;
