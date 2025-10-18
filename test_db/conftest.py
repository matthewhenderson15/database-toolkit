"""
Shared test fixtures and configuration for database tests.

This module provides common fixtures that can be used across all database test files
to avoid code duplication and ensure consistent test setup.
"""

import pathlib
import tempfile
from typing import Iterator

import pytest

from src.config.database import DatabaseManager, DBConnection


@pytest.fixture
def temp_db_path() -> Iterator[pathlib.Path]:
    """
    Create a temporary database file for testing and removes automatically after the test.

    Yields:
        pathlib.Path: Path to the temporary database file
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = pathlib.Path(f.name)
    yield db_path

    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def temp_dir() -> Iterator[pathlib.Path]:
    """
    Create a temporary directory for testing.

    Yields:
        pathlib.Path: Path to the temporary directory

    Cleanup:
        Automatically removes the temporary directory after the test
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        yield pathlib.Path(temp_dir)


@pytest.fixture
def db_connection(temp_db_path: pathlib.Path) -> Iterator[DBConnection]:
    """
    Create a basic DBConnection instance for testing.

    Args:
        temp_db_path: Temporary database file path from temp_db_path fixture

    Yields:
        DBConnection: Configured database connection instance
    """
    db_conn = DBConnection(file_system=temp_db_path, pool_size=2)
    yield db_conn
    db_conn.close()


@pytest.fixture
def memory_db_connection() -> Iterator[DBConnection]:
    """
    Create an in-memory DBConnection instance for testing.

    Yields:
        DBConnection: In-memory database connection instance
    """
    db_conn = DBConnection(in_memory=True, pool_size=2)
    yield db_conn
    db_conn.close()


@pytest.fixture
def db_manager(temp_db_path: pathlib.Path) -> Generator[DatabaseManager, None, None]:
    """
    Create a DatabaseManager instance with a test table for testing.

    Args:
        temp_db_path: Temporary database file path from temp_db_path fixture

    Yields:
        DatabaseManager: Configured database manager with test table

    Setup:
        Creates a test_table with id, name, age, and email columns

    Cleanup:
        Automatically closes the database manager after the test
    """
    db_mgr = DatabaseManager(file_system=temp_db_path, pool_size=2)

    # Create a standard test table for use across tests
    with db_mgr.get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_table (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                age INTEGER,
                email TEXT UNIQUE
            )
        """)
        conn.commit()

    yield db_mgr
    db_mgr.close()


@pytest.fixture
def memory_db_manager() -> Generator[DatabaseManager, None, None]:
    """
    Create an in-memory DatabaseManager instance with a test table.

    Yields:
        DatabaseManager: In-memory database manager with test table

    Setup:
        Creates a test_table with id, name, age, and email columns

    Cleanup:
        Automatically closes the database manager after the test
    """
    db_mgr = DatabaseManager(in_memory=True, pool_size=2)

    # Create a standard test table for use across tests
    with db_mgr.get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_table (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                age INTEGER,
                email TEXT UNIQUE
            )
        """)
        conn.commit()

    yield db_mgr
    db_mgr.close()


@pytest.fixture
def populated_db_manager(db_manager: DatabaseManager) -> DatabaseManager:
    """
    Create a DatabaseManager with pre-populated test data.

    Args:
        db_manager: DatabaseManager instance from db_manager fixture

    Returns:
        DatabaseManager: The same manager but with test data inserted

    Setup:
        Inserts 5 test users with varying ages and unique emails
    """
    test_data = [
        ("Alice Johnson", 28, "alice@example.com"),
        ("Bob Smith", 35, "bob@example.com"),
        ("Charlie Brown", 22, "charlie@example.com"),
        ("Diana Prince", 30, "diana@example.com"),
        ("Eve Adams", 25, "eve@example.com"),
    ]

    for name, age, email in test_data:
        db_manager._execute(
            "INSERT INTO test_table (name, age, email) VALUES (?, ?, ?)",
            (name, age, email),
        )

    return db_manager


@pytest.fixture
def single_connection_db(
    temp_db_path: pathlib.Path,
) -> Generator[DBConnection, None, None]:
    """
    Create a DBConnection with a single connection for testing pool exhaustion.

    Args:
        temp_db_path: Temporary database file path from temp_db_path fixture

    Yields:
        DBConnection: Database connection with pool_size=1

    Cleanup:
        Automatically closes the connection after the test
    """
    db_conn = DBConnection(file_system=temp_db_path, pool_size=1, timeout=0.1)
    yield db_conn
    db_conn.close()


@pytest.fixture
def large_pool_db(temp_db_path: pathlib.Path) -> Generator[DBConnection, None, None]:
    """
    Create a DBConnection with a large connection pool for concurrency testing.

    Args:
        temp_db_path: Temporary database file path from temp_db_path fixture

    Yields:
        DBConnection: Database connection with pool_size=5

    Cleanup:
        Automatically closes the connection after the test
    """
    db_conn = DBConnection(
        file_system=temp_db_path, pool_size=5, check_same_thread=False
    )
    yield db_conn
    db_conn.close()


class TestDataHelper:
    """
    Helper class providing common test data and utility methods.
    """

    @staticmethod
    def sample_users():
        """
        Get sample user data for testing.

        Returns:
            list: List of tuples containing (name, age, email)
        """
        return [
            ("John Doe", 30, "john@example.com"),
            ("Jane Smith", 25, "jane@example.com"),
            ("Bob Johnson", 35, "bob@example.com"),
            ("Alice Brown", 28, "alice@example.com"),
            ("Charlie Wilson", 32, "charlie@example.com"),
        ]

    @staticmethod
    def large_text_data(size: int = 10000) -> str:
        """
        Generate large text data for testing.

        Args:
            size: Number of characters to generate

        Returns:
            str: Large text string
        """
        return "x" * size

    @staticmethod
    def sql_injection_attempts():
        """
        Get common SQL injection attempt strings for testing.

        Returns:
            list: List of malicious SQL strings
        """
        return [
            "'; DROP TABLE test_table; --",
            "' OR '1'='1",
            "'; DELETE FROM test_table; --",
            "' UNION SELECT * FROM test_table; --",
        ]


@pytest.fixture
def test_data_helper():
    """
    Provide access to TestDataHelper methods in tests.

    Returns:
        TestDataHelper: Instance of the helper class
    """
    return TestDataHelper()


# Custom pytest markers for organizing tests
def pytest_configure(config):
    """
    Register custom pytest markers.
    """
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line(
        "markers", "connection: marks tests related to database connections"
    )
    config.addinivalue_line("markers", "query: marks tests related to query execution")
    config.addinivalue_line("markers", "builder: marks tests related to query builders")
    config.addinivalue_line("markers", "error: marks tests related to error handling")
