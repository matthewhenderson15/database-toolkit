import pathlib
import tempfile

import pytest

from src.config import database


class Setup:
    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file for testing. Destroy after creating."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = pathlib.Path(f.name)
        yield db_path

        if db_path.exists():
            db_path.unlink()

    @pytest.fixture
    def in_memory_db(self):
        """Create an in-memory database for testing."""
        with database.DatabaseManager(in_memory=True) as manager:
            yield manager

    @pytest.fixture
    def file_path_db(self):
        """Create a SQLite3 database instance using a temp DB path."""
        with database.DatabaseManager(file_system=self.temp_db_path()) as manager:
            yield manager

    @pytest.fixture
    def create_test_table(self, in_memory: bool):
        """Create a test table to use for testing the"""
        create_query = database.DDLQueryBuilder.create(
            table="test_users",
            columns=[
                ("id", "INTEGER"),
                ("name", "STRING"),
                ("created_at", "TIMESTAMP"),
                ("updated_at", "TIMESTAMP"),
            ],
        )

        insert_query = database.DMLQueryBuilder.insert(
            columns=["id", "name", "created_at", "updated_at"], table="test_users"
        )

        with database.DatabaseManager() as manager:
            manager._execute(query=create_query)
            manager._execute(query=insert_query)
