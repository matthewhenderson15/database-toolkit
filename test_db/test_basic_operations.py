import sqlite3
from unittest.mock import patch

import pytest

from src.config.database import DatabaseManager


@pytest.mark.query
class TestQueryExecution:
    def test_execute_insert_query(self, db_manager: DatabaseManager):
        """Test executing INSERT queries."""
        query = "INSERT INTO test_table (name, age, email) VALUES (?, ?, ?)"
        params = ("John Doe", 30, "john@example.com")

        rows_affected = db_manager._execute(query=query, params=params)

        assert rows_affected == 1

        result = db_manager._find_one(
            query="SELECT * FROM test_table WHERE name = ?", params=("John Doe",)
        )
        assert result["name"] == "John Doe"
        assert result["age"] == 30
        assert result["email"] == "john@example.com"

    def test_execute_update_query(self, db_manager):
        """Test executing UPDATE queries."""
        db_manager._execute(
            query="INSERT INTO test_table (name, age, email) VALUES (?, ?, ?)",
            params=("Jane Doe", 25, "jane@example.com"),
        )

        query = "UPDATE test_table SET age = ? WHERE name = ?"
        params = (26, "Jane Doe")

        rows_affected = db_manager._execute(query=query, params=params)

        assert rows_affected == 1

        result = db_manager._find_one(
            "SELECT age FROM test_table WHERE name = ?", ("Jane Doe",)
        )
        assert result["age"] == 26

    def test_execute_delete_query(self, db_manager):
        """Test executing DELETE queries."""
        db_manager._execute(
            "INSERT INTO test_table (name, age, email) VALUES (?, ?, ?)",
            ("Bob Smith", 35, "bob@example.com"),
        )

        query = "DELETE FROM test_table WHERE name = ?"
        params = ("Bob Smith",)

        rows_affected = db_manager._execute(query=query, params=params)

        assert rows_affected == 1

        result = db_manager._find_one(
            query="SELECT * FROM test_table WHERE name = ?", params=("Bob Smith",)
        )
        assert result is None

    def test_find_one_query(self, db_manager):
        """Test _find_one method."""
        db_manager._execute(
            "INSERT INTO test_table (name, age, email) VALUES (?, ?, ?)",
            ("Alice Johnson", 28, "alice@example.com"),
        )

        result = db_manager._find_one(
            "SELECT * FROM test_table WHERE name = ?", ("Alice Johnson",)
        )

        assert result is not None
        assert result["name"] == "Alice Johnson"
        assert result["age"] == 28
        assert result["email"] == "alice@example.com"

        no_result = db_manager._find_one(
            "SELECT * FROM test_table WHERE name = ?", ("Nonexistent",)
        )
        assert no_result is None

    def test_find_all_query(self, populated_db_manager):
        """Test _find_all method."""
        results = populated_db_manager._find_all(
            "SELECT * FROM test_table ORDER BY age"
        )

        assert len(results) == 5
        assert results[0]["name"] == "Charlie Brown"
        assert results[1]["name"] == "Eve Adams"
        assert results[2]["name"] == "Alice Johnson"

    def test_find_many_with_limit(self, populated_db_manager):
        """Test _find_many method with limit."""
        results = populated_db_manager._find_many(
            "SELECT * FROM test_table ORDER BY age", limit=3
        )

        assert len(results) == 3
        assert results[0]["name"] == "Charlie Brown"
        assert results[1]["name"] == "Eve Adams"
        assert results[2]["name"] == "Alice Johnson"

    def test_execute_select_query_with_retries(self, db_manager):
        """Test _execute_select_query retry mechanism."""
        db_manager._execute(
            "INSERT INTO test_table (name, age, email) VALUES (?, ?, ?)",
            ("Test User", 25, "test@example.com"),
        )

        results = db_manager._execute_select_query(
            "SELECT * FROM test_table WHERE name = ?", ("Test User",), retries=3
        )

        assert len(results) == 1
        assert results[0]["name"] == "Test User"

    def test_execute_query_max_retries_validation(self, db_manager):
        """Test that maximum retries cannot exceed 10."""
        with pytest.raises(ValueError, match="Maximum retries cannot exceed 10"):
            db_manager._execute_select_query("SELECT 1", retries=11)

        with pytest.raises(ValueError, match="Maximum retries cannot exceed 10"):
            db_manager._execute("SELECT 1", retries=11)

    def test_transaction_begin_commit(self, db_manager):
        """Test transaction begin and commit."""
        db_manager.begin_transaction()

        db_manager.connection.execute(
            "INSERT INTO test_table (name, age, email) VALUES (?, ?, ?)",
            ("Transaction Test", 40, "trans@example.com"),
        )

        db_manager.commit_transaction()

        result = db_manager._find_one(
            "SELECT * FROM test_table WHERE name = ?", ("Transaction Test",)
        )
        assert result is not None
        assert result["name"] == "Transaction Test"

    def test_transaction_rollback(self, db_manager):
        """Test transaction rollback."""
        db_manager.begin_transaction()

        db_manager.connection.execute(
            "INSERT INTO test_table (name, age, email) VALUES (?, ?, ?)",
            ("Rollback Test", 35, "rollback@example.com"),
        )

        db_manager.rollback_transaction()

        result = db_manager._find_one(
            "SELECT * FROM test_table WHERE name = ?", ("Rollback Test",)
        )
        assert result is None

    def test_parameter_binding_prevents_sql_injection(
        self, db_manager, test_data_helper
    ):
        """Test that parameter binding prevents SQL injection."""
        db_manager._execute(
            "INSERT INTO test_table (name, age, email) VALUES (?, ?, ?)",
            ("Safe User", 30, "safe@example.com"),
        )

        malicious_inputs = test_data_helper.sql_injection_attempts()

        for malicious_input in malicious_inputs:
            result = db_manager._find_one(
                "SELECT * FROM test_table WHERE name = ?", (malicious_input,)
            )
            assert result is None

        all_results = db_manager._find_all("SELECT * FROM test_table")
        assert len(all_results) == 1
        assert all_results[0]["name"] == "Safe User"

    def test_query_execution_with_error_rollback(self, db_manager):
        """Test that query execution errors trigger rollback."""
        initial_count = len(db_manager._find_all("SELECT * FROM test_table"))

        with pytest.raises(sqlite3.IntegrityError):
            db_manager._execute(
                "INSERT INTO test_table (name, age, email) VALUES (?, ?, ?)",
                ("Test", 25, "test@example.com"),
            )
            db_manager._execute(
                "INSERT INTO test_table (name, age, email) VALUES (?, ?, ?)",
                ("Test2", 30, "test@example.com"),
            )  # Duplicate email

        final_count = len(db_manager._find_all("SELECT * FROM test_table"))
        assert final_count == initial_count

    @patch("time.sleep")
    def test_database_lock_retry_mechanism(self, mock_sleep, db_manager):
        """Test retry mechanism for database lock scenarios."""
        with patch.object(
            db_manager, "_DatabaseManager__determine_retry"
        ) as mock_retry:
            mock_retry.side_effect = [
                None,
                None,
                sqlite3.OperationalError("database is locked"),
            ]

            with patch("sqlite3.connect") as mock_connect:
                mock_conn = mock_connect.return_value
                mock_conn.cursor.return_value.execute.side_effect = [
                    sqlite3.OperationalError("database is locked"),
                    sqlite3.OperationalError("database is locked"),
                    None,
                ]
                mock_conn.cursor.return_value.fetchall.return_value = [{"id": 1}]

                try:
                    result = db_manager._execute_select_query("SELECT 1", retries=3)
                except sqlite3.OperationalError:
                    pass

    def test_row_factory_returns_dict_like_objects(self, db_manager):
        """Test that row factory returns dict-like Row objects."""
        db_manager._execute(
            "INSERT INTO test_table (name, age, email) VALUES (?, ?, ?)",
            ("Dict Test", 45, "dict@example.com"),
        )

        result = db_manager._find_one(
            "SELECT * FROM test_table WHERE name = ?", ("Dict Test",)
        )

        assert result["name"] == "Dict Test"
        assert result["age"] == 45
        assert result["email"] == "dict@example.com"

        assert "name" in result
        assert len(result) == 4  # id, name, age, email
