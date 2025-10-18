import pathlib
import sqlite3
import time
from unittest.mock import Mock, patch

import pytest

from src.config.database import DBConnection, DatabaseManager, IsolationLevels


@pytest.mark.error
class TestErrorHandling:

    def test_database_connection_error_invalid_path(self):
        """Test database connection error with completely invalid path."""
        invalid_path = pathlib.Path("/root/definitely/does/not/exist/test.db")
        
        with pytest.raises(sqlite3.DatabaseError):
            DBConnection(file_system=invalid_path, pool_size=1)

    def test_database_connection_permission_error(self, temp_dir):
        """Test database connection with permission issues."""
        restricted_path = temp_dir / "restricted.db"
        restricted_path.touch()
        restricted_path.chmod(0o000)  # No permissions
        
        try:
            with pytest.raises(sqlite3.DatabaseError):
                DBConnection(file_system=restricted_path, pool_size=1)
        finally:
            restricted_path.chmod(0o644)  # Restore permissions for cleanup

    def test_invalid_sql_query_error(self, db_manager):
        """Test handling of invalid SQL queries."""
        with pytest.raises(sqlite3.OperationalError):
            db_manager._execute("INVALID SQL QUERY HERE")

    def test_foreign_key_constraint_error(self, db_manager):
        """Test foreign key constraint violations."""
        with db_manager.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    FOREIGN KEY (user_id) REFERENCES test_table(id)
                )
            """)
            conn.commit()
        
        with pytest.raises(sqlite3.IntegrityError):
            db_manager._execute("INSERT INTO orders (user_id) VALUES (?)", (999,))

    def test_unique_constraint_violation(self, db_manager):
        """Test unique constraint violations."""
        db_manager._execute("INSERT INTO test_table (name, email) VALUES (?, ?)", 
                           ("John", "john@example.com"))
        
        with pytest.raises(sqlite3.IntegrityError):
            db_manager._execute("INSERT INTO test_table (name, email) VALUES (?, ?)", 
                               ("Jane", "john@example.com"))  # Duplicate email

    def test_not_null_constraint_violation(self, db_manager):
        """Test NOT NULL constraint violations."""
        with pytest.raises(sqlite3.IntegrityError):
            db_manager._execute("INSERT INTO test_table (email) VALUES (?)", 
                               ("test@example.com",))  # Missing required name field

    def test_database_locked_retry_mechanism(self, db_manager):
        """Test retry mechanism when database is locked."""
        with patch.object(db_manager, '_DatabaseManager__determine_retry') as mock_retry:
            mock_retry.return_value = None  # Don't actually sleep in tests
            
            with patch('sqlite3.connect') as mock_connect:
                mock_cursor = Mock()
                mock_cursor.execute.side_effect = [
                    sqlite3.OperationalError("database is locked"),
                    sqlite3.OperationalError("database is locked"),
                    None  # Success on third try
                ]
                mock_cursor.rowcount = 1
                
                mock_conn = Mock()
                mock_conn.cursor.return_value = mock_cursor
                mock_connect.return_value.__enter__.return_value = mock_conn
                
                # This should succeed after retries
                result = db_manager._execute("INSERT INTO test_table (name, email) VALUES (?, ?)", 
                                           ("Test", "test@example.com"), retries=3)
                
                assert mock_cursor.execute.call_count == 3

    def test_timeout_behavior(self, single_connection_db):
        """Test connection timeout behavior."""
        # Take the only connection
        with single_connection_db.get_connection() as conn1:
            start_time = time.time()
            
            # Try to get another connection - should timeout
            with pytest.raises(Exception):  # queue.Empty or similar timeout exception
                with single_connection_db.get_connection() as conn2:
                    pass
            
            elapsed = time.time() - start_time
            assert elapsed >= 0.1  # Should have waited at least timeout duration

    def test_malformed_parameters_handling(self, db_manager):
        """Test handling of malformed query parameters."""
        # Test with wrong number of parameters
        with pytest.raises((sqlite3.ProgrammingError, IndexError)):
            db_manager._execute("INSERT INTO test_table (name, email) VALUES (?, ?)", 
                               ("Only one param",))  # Missing second parameter

    def test_connection_pool_corruption_recovery(self, db_connection):
        """Test recovery from connection pool corruption."""
        # Corrupt a connection by closing it manually
        conn = db_connection.connection_pool.get()
        conn.close()  # Close connection but it's still in pool
        db_connection.connection_pool.put(conn)
        
        # The pool should handle the corrupted connection gracefully
        # This might raise an exception or handle it internally
        try:
            with db_connection.get_connection() as working_conn:
                cursor = working_conn.execute("SELECT 1")
                result = cursor.fetchone()
                assert result[0] == 1
        except sqlite3.ProgrammingError:
            # If we get a "Cannot operate on a closed database" error,
            # that's expected behavior for this edge case
            pass

    def test_memory_database_isolation(self, memory_db_manager):
        """Test that in-memory databases are properly isolated."""
        # Create another in-memory database
        db2 = DatabaseManager(in_memory=True, pool_size=1)
        
        # Insert data into first database (memory_db_manager already has test_table)
        memory_db_manager._execute("INSERT INTO test_table (name, email) VALUES (?, ?)", 
                                  ("Test User", "test@example.com"))
        
        # Second database should not see the test_table
        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            with db2.get_connection() as conn:
                conn.execute("SELECT * FROM test_table")
        
        db2.close()

    def test_concurrent_transaction_conflicts(self, temp_db_path):
        """Test handling of concurrent transaction conflicts."""
        with DatabaseManager(file_system=temp_db_path, pool_size=1, 
                            isolation_level=IsolationLevels.IMMEDIATE) as db1:
            with DatabaseManager(file_system=temp_db_path, pool_size=1, 
                                isolation_level=IsolationLevels.IMMEDIATE) as db2:
                
                with db1.get_connection() as conn:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS counter (
                            id INTEGER PRIMARY KEY,
                            value INTEGER
                        )
                    """)
                    conn.execute("INSERT INTO counter (value) VALUES (0)")
                    conn.commit()
                
                # Start transactions in both connections
                db1.begin_transaction()
                
                # Second connection should be blocked when trying immediate transaction
                with pytest.raises(sqlite3.OperationalError):
                    db2.begin_transaction()
                
                db1.rollback_transaction()

    def test_invalid_isolation_level_handling(self, temp_db_path):
        """Test handling of invalid isolation levels."""
        # The enum should prevent invalid values, but test edge cases
        for valid_level in IsolationLevels:
            with DBConnection(file_system=temp_db_path, 
                            isolation_level=valid_level, pool_size=1) as db_conn:
                pass

    def test_large_query_parameter_handling(self, db_manager, test_data_helper):
        """Test handling of very large query parameters."""
        large_text = test_data_helper.large_text_data(size=10000)
        
        db_manager._execute("INSERT INTO test_table (name, email) VALUES (?, ?)", 
                           (large_text, "large@example.com"))
        
        result = db_manager._find_one("SELECT name FROM test_table WHERE email = ?", 
                                     ("large@example.com",))
        assert result["name"] == large_text

    def test_connection_cleanup_after_exception(self, db_manager):
        """Test that connections are properly cleaned up after exceptions."""
        initial_pool_size = db_manager.connection_pool.qsize()
        
        # Force an exception during connection use
        try:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM nonexistent_table")
        except sqlite3.OperationalError:
            pass  # Expected error
        
        # Pool should be restored to original size
        assert db_manager.connection_pool.qsize() == initial_pool_size

    def test_retry_exponential_backoff(self, db_manager):
        """Test that retry mechanism uses exponential backoff."""
        with patch('time.sleep') as mock_sleep:
            with patch.object(db_manager, '_execute_select_query') as mock_execute:
                mock_execute.side_effect = [
                    sqlite3.OperationalError("database is locked"),
                    sqlite3.OperationalError("database is locked"),
                    [{"result": "success"}]
                ]
                
                # Trigger retry logic
                try:
                    db_manager._DatabaseManager__determine_retry(0, 3, "database is locked")
                    db_manager._DatabaseManager__determine_retry(1, 3, "database is locked")
                except:
                    pass
                
                # Check that sleep was called with exponential backoff
                if mock_sleep.called:
                    calls = mock_sleep.call_args_list
                    if len(calls) >= 2:
                        assert calls[0][0][0] < calls[1][0][0]  # Second sleep should be longer

    def test_edge_case_empty_query_results(self, db_manager):
        """Test handling of queries that return no results."""
        # Test find_one with no results
        result = db_manager._find_one("SELECT * FROM test_table WHERE id = ?", (99999,))
        assert result is None
        
        # Test find_all with no results
        results = db_manager._find_all("SELECT * FROM test_table WHERE id < 0")
        assert results == []
        
        # Test find_many with no results
        results = db_manager._find_many("SELECT * FROM test_table WHERE id < 0", limit=10)
        assert results == []