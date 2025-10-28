import sqlite3
import threading
import time

import pytest

from src.config.database import DBConnection, IsolationLevels


@pytest.mark.connection
class TestDBConnection:
    def test_file_connection_success(self, db_connection: DBConnection):
        """Test successful file-based database connection."""
        assert not db_connection.in_memory
        assert db_connection.pool_size == 2
        assert db_connection.connection_pool.qsize() == 2

        with db_connection.get_connection() as conn:
            cursor = conn.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

    def test_memory_connection_success(self, memory_db_connection: DBConnection):
        """Test successful in-memory database connection."""
        assert memory_db_connection.in_memory
        assert memory_db_connection.pool_size == 2
        assert memory_db_connection.connection_pool.qsize() == 2

        with memory_db_connection.get_connection() as conn:
            cursor = conn.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

    def test_connection_pool_initialization(self, large_pool_db: DBConnection):
        """Test that connection pool is properly initialized."""
        pool_size = 5

        assert large_pool_db.connection_pool.qsize() == pool_size

        connections = []
        for i in range(pool_size):
            conn = large_pool_db.connection_pool.get()
            connections.append(conn)
            assert isinstance(conn, sqlite3.Connection)

        for conn in connections:
            large_pool_db.connection_pool.put(conn)

    def test_connection_pool_exhaustion(self, single_connection_db):
        """Test behavior when connection pool is exhausted."""
        with single_connection_db.get_connection() as conn1:
            start_time = time.time()
            with pytest.raises(Exception):
                with single_connection_db.get_connection() as conn2:
                    pass
            elapsed = time.time() - start_time
            assert elapsed >= 0.1

    def test_context_manager_functionality(self, temp_db_path):
        """Test DBConnection as context manager."""
        with DBConnection(file_system=temp_db_path, pool_size=2) as db_conn:
            assert db_conn.connection_pool.qsize() == 2

            with db_conn.get_connection() as conn:
                cursor = conn.execute("SELECT 1")
                result = cursor.fetchone()
                assert result[0] == 1

    def test_connection_pool_thread_safety(self, large_pool_db):
        """Test that connection pool works correctly with multiple threads."""
        results = []
        errors = []

        def worker(worker_id):
            try:
                with large_pool_db.get_connection() as conn:
                    cursor = conn.execute("SELECT ?", (worker_id,))
                    result = cursor.fetchone()
                    results.append(result[0])
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0
        assert sorted(results) == [0, 1, 2, 3, 4]

    def test_isolation_levels(self, temp_db_path):
        """Test different isolation levels."""
        for isolation_level in IsolationLevels:
            with DBConnection(
                file_system=temp_db_path, isolation_level=isolation_level, pool_size=1
            ) as db_conn:
                with db_conn.get_connection() as conn:
                    cursor = conn.execute("SELECT 1")
                    result = cursor.fetchone()
                    assert result[0] == 1

    def test_pragma_settings_applied(self, db_connection):
        """Test that PRAGMA settings are correctly applied."""
        with db_connection.get_connection() as conn:
            foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            synchronous = conn.execute("PRAGMA synchronous").fetchone()[0]
            temp_store = conn.execute("PRAGMA temp_store").fetchone()[0]

            assert foreign_keys == 1
            assert journal_mode == "wal"
            assert synchronous == 1  # NORMAL
            assert temp_store == 2  # MEMORY

    def test_invalid_path_fails_gracefully(self, temp_dir):
        """Test that invalid paths are handled gracefully."""
        invalid_path = temp_dir / "nonexistent" / "directory" / "test.db"

        with pytest.raises(sqlite3.DatabaseError):
            DBConnection(file_system=invalid_path, pool_size=1)

    def test_connection_cleanup_on_error(self, db_connection):
        """Test that connections are properly cleaned up when errors occur."""
        initial_pool_size = db_connection.connection_pool.qsize()

        try:
            with db_connection.get_connection() as conn:
                raise ValueError("Test error")
        except ValueError:
            pass

        assert db_connection.connection_pool.qsize() == initial_pool_size
