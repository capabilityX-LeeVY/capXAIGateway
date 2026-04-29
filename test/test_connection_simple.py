#!/usr/bin/env python3
"""
Simple database connection test without the logging system
"""

import pymysql
import json
import os

def test_connection():
    # Load config directly
    config_path = "config/db_config.json"
    
    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
            
        db_config = config_data['dbConfig']['capx_ai_gateway_db']
        print(f"🔍 Testing connection to: {db_config['host']}:{db_config['port']}")
        
        # Test connection
        connection = pymysql.connect(**db_config)
        print("✅ Connection successful!")
        
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            print(f"✅ Test query result: {result}")
            
            # Check if session_info table exists
            cursor.execute("SHOW TABLES LIKE 'session_info'")
            table_exists = cursor.fetchone() is not None
            print(f"✅ session_info table exists: {table_exists}")
        
        connection.close()
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    success = test_connection()
    exit(0 if success else 1)
