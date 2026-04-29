"""
Bug Data Reader Module

Provides functionality to read and categorize bugs from MySQL database.
This module can be easily ported to other projects.

Author: AI Gateway Development Team
Date: April 3, 2026
"""

import logging
from typing import Dict, List, Tuple, Set, Optional

logger = logging.getLogger(__name__)


class BugDataReader:
    """
    Bug Data Reader - Reads bugs from database and categorizes them as new or existing
    
    Features:
    - Reads bug data from MySQL database
    - Categorizes bugs into new (first-time seen) and existing (previously processed)
    - Tracks processed bugs in memory
    - Cleans up deleted bugs from cache
    - Supports incremental processing
    
    Usage:
        reader = BugDataReader(db_connection)
        new_bugs, existing_bugs = reader.get_new_and_existing_bugs()
    """
    
    def __init__(self, db_connection, table_name: str = "issue_by_capx_demo"):
        """
        Initialize Bug Data Reader
        
        Args:
            db_connection: Database connection object with Query() method
            table_name: Name of the bug table (default: "issue_by_capx_demo")
        """
        self.db_connection = db_connection
        self.table_name = table_name
        self.processed_bugs: Set[str] = set()  # Set of processed bug IDs
        
        logger.info(f"🔧 BugDataReader initialized (table: {table_name})")
    
    def get_new_and_existing_bugs(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Get new bugs and existing bugs from database
        
        This method:
        1. Queries all bugs from database
        2. Categorizes bugs as "new" (first-time seen) or "existing" (previously processed)
        3. Tracks bug IDs in memory (self.processed_bugs)
        4. Cleans up deleted bugs from memory cache
        
        Returns:
            Tuple of (new_bugs, existing_bugs)
            - new_bugs: List of bugs seen for the first time
            - existing_bugs: List of bugs that were processed before
            
        Example:
            new_bugs, existing_bugs = reader.get_new_and_existing_bugs()
            print(f"Found {len(new_bugs)} new bugs, {len(existing_bugs)} existing bugs")
        """
        try:
            if not self.db_connection:
                logger.error("❌ Database connection not initialized")
                return [], []
            
            # Query all bugs from database
            sql = f"""
                SELECT jiraID, title, createDate, affectVersion, platform, status, 
                       type, testSuite, testCase, step_num
                FROM {self.table_name}
                ORDER BY createDate DESC
            """
            
            results, columns = self.db_connection.Query(sql)
            
            new_bugs = []
            existing_bugs = []
            current_bug_ids = set()
            
            # Process each bug from database
            for row in results:
                jira_id = row[0]
                current_bug_ids.add(jira_id)
                
                # Build bug dictionary
                bug = {
                    'jiraID': jira_id,
                    'title': row[1],
                    'createDate': row[2],
                    'affectVersion': row[3],
                    'platform': row[4],
                    'status': row[5],  # Database status
                    'db_status': row[5],  # Backup field for compatibility
                    'type': row[6],
                    'testSuite': row[7],
                    'testCase': row[8],
                    'step_num': row[9]
                }
                
                # Categorize as new or existing
                if jira_id not in self.processed_bugs:
                    # First time seeing this bug - mark as NEW
                    new_bugs.append(bug)
                    self.processed_bugs.add(jira_id)
                    logger.debug(f"🆕 New bug detected: {jira_id}")
                else:
                    # Previously processed bug - mark as EXISTING
                    existing_bugs.append(bug)
            
            # Clean up deleted bugs (bugs removed from database)
            deleted_bugs = self.processed_bugs - current_bug_ids
            if deleted_bugs:
                logger.info(f"🗑️ Found {len(deleted_bugs)} deleted bugs, removing from cache")
                for bug_id in deleted_bugs:
                    self.processed_bugs.discard(bug_id)
            
            # Log summary
            logger.info(f"📊 Retrieved {len(results)} bugs from database")
            logger.info(f"   🆕 New bugs: {len(new_bugs)}")
            logger.info(f"   📋 Existing bugs: {len(existing_bugs)}")
            logger.info(f"   🗑️ Deleted bugs: {len(deleted_bugs)}")
            logger.debug(f"   🧠 Total processed bugs in memory: {len(self.processed_bugs)}")
            
            return new_bugs, existing_bugs
            
        except Exception as e:
            logger.error(f"❌ Failed to get bug list: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return [], []
    
    def get_all_bugs(self) -> List[Dict]:
        """
        Get all bugs from database without categorization
        
        Returns:
            List of all bugs
        """
        new_bugs, existing_bugs = self.get_new_and_existing_bugs()
        return new_bugs + existing_bugs
    
    def clear_cache(self):
        """
        Clear the processed bugs cache
        
        After calling this, all bugs will be treated as "new" in the next query
        """
        self.processed_bugs.clear()
        logger.info("🧹 Processed bugs cache cleared")
    
    def get_cache_size(self) -> int:
        """
        Get the number of bugs currently tracked in memory
        
        Returns:
            Number of processed bugs
        """
        return len(self.processed_bugs)
    
    def is_bug_processed(self, jira_id: str) -> bool:
        """
        Check if a bug has been processed before
        
        Args:
            jira_id: JIRA issue ID
            
        Returns:
            True if bug was processed before, False otherwise
        """
        return jira_id in self.processed_bugs
    
    def mark_bug_as_processed(self, jira_id: str):
        """
        Manually mark a bug as processed
        
        Args:
            jira_id: JIRA issue ID
        """
        self.processed_bugs.add(jira_id)
        logger.debug(f"✅ Marked {jira_id} as processed")
    
    def get_statistics(self) -> Dict:
        """
        Get statistics about the bug data reader
        
        Returns:
            Dictionary containing statistics
        """
        return {
            'total_processed_bugs': len(self.processed_bugs),
            'processed_bug_ids': sorted(list(self.processed_bugs)),
            'table_name': self.table_name
        }


def create_bug_reader(db_connection, table_name: str = "issue_by_capx_demo") -> BugDataReader:
    """
    Factory function to create a BugDataReader instance
    
    Args:
        db_connection: Database connection object
        table_name: Name of the bug table
        
    Returns:
        BugDataReader instance
        
    Example:
        from jira_gateway.tojirabug import MysqlConnection
        
        db_conn = MysqlConnection('host', 3306, 'user', 'pass', 'db')
        reader = create_bug_reader(db_conn)
        new_bugs, existing_bugs = reader.get_new_and_existing_bugs()
    """
    return BugDataReader(db_connection, table_name)


# Example usage
if __name__ == "__main__":
    """
    Example usage of BugDataReader
    
    This demonstrates how to use the module in a standalone script
    """
    import sys
    import os
    
    # Add parent directory to path for imports
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    
    from jira_gateway.tojirabug import MysqlConnection
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize database connection
    db_host = 'capx-dev.capx.com'
    db_port = 3306
    db_user = 'test'
    db_password = 'pass'
    db_name = 'issue_db'
    
    try:
        db_connection = MysqlConnection(db_host, db_port, db_user, db_password, db_name)
        
        # Create bug reader
        reader = create_bug_reader(db_connection)
        
        # First run - all bugs will be "new"
        print("\n" + "="*60)
        print("FIRST RUN - Initial data load")
        print("="*60)
        new_bugs, existing_bugs = reader.get_new_and_existing_bugs()
        
        print(f"\n📊 Results:")
        print(f"   New bugs: {len(new_bugs)}")
        print(f"   Existing bugs: {len(existing_bugs)}")
        print(f"\n🆕 Sample new bugs:")
        for bug in new_bugs[:3]:
            print(f"   - {bug['jiraID']}: {bug['title'][:50]}...")
        
        # Second run - same bugs will be "existing"
        print("\n" + "="*60)
        print("SECOND RUN - Incremental update")
        print("="*60)
        new_bugs, existing_bugs = reader.get_new_and_existing_bugs()
        
        print(f"\n📊 Results:")
        print(f"   New bugs: {len(new_bugs)}")
        print(f"   Existing bugs: {len(existing_bugs)}")
        
        # Print statistics
        print("\n" + "="*60)
        print("STATISTICS")
        print("="*60)
        stats = reader.get_statistics()
        print(f"Total processed bugs: {stats['total_processed_bugs']}")
        print(f"Table name: {stats['table_name']}")
        
    except Exception as e:
        logger.error(f"❌ Example execution failed: {e}")
        import traceback
        traceback.print_exc()
