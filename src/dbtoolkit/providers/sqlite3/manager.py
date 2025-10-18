from __future__ import annotations

import sqlite3
import time
from typing import List, Optional

from connection import DBConnection


class DatabaseManager(DBConnection):
    def __init__(self, **kwargs):
        """
        Initialize DatabaseManager with connection parameters.

        Args:
            **kwargs: Parameters passed to DBConnection constructor
        """
        super().__init__(**kwargs)

    def _execute_transaction(self, query_and_params: List[tuple]) -> int:
        """
        Executes multiple queries in a transaction.

        Params:
            query_and_params (List, tuple):

        Returns:
            Number of rows affected in the transaction.
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
        except:
            pass

    def _execute_select_query(
        self, query: str, params: Optional[tuple] = None, retries: int = 3
    ) -> List[sqlite3.Row]:
        """
        Executes a query up to a certain number of retries.

        Params:
            query (str): The SQL query to be executed.
            params (tuple, optional): Parameters for the query (prevents SQL injection).
            retries (int): Number of retries for a query (max 10).

        Returns:
            List of row results from the SQLite3 database.

        Raises:
            ValueError: If retries > 10.
            sqlite3.OperationalError: If database operations fail after retries.
        """
        if retries > 10:
            raise ValueError("Maximum retries cannot exceed 10")

        for attempt in range(retries):
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()

                    cursor.execute(sql=query, parameters=params or ())
                    rows = cursor.fetchall()

                    self.logger.info(
                        f"Successfully fetched {len(rows)} rows for query: {query}"
                    )

                return rows
            except sqlite3.OperationalError as e:
                self.__determine_retry(attempt=attempt, retries=retries, e=e)
                continue
            finally:
                if cursor:
                    cursor.close()

    def _execute(
        self, query: str, params: Optional[tuple] = None, retries: int = 3
    ) -> int:
        """
        Execute a query that doesn't return rows (e.g., INSERT, UPDATE, DELETE).

        Args:
            query (str): The SQL query to be executed.
            params (tuple, optional): Parameters for the query to prevent SQL injection.
            retries (int): Number of retries for a query (max 10).

        Returns:
            Number of rows affected.

        Raises:
            ValueError: If retries > 10.
            sqlite3.OperationalError: If database operations fail after retries.
        """
        if retries > 10:
            raise ValueError("Maximum retries cannot exceed 10")

        for attempt in range(retries):
            try:
                with self.get_connection() as conn:
                    try:
                        cursor = conn.cursor()

                        cursor.execute(sql=query, parameters=params or ())
                        conn.commit()

                        return cursor.rowcount
                    except Exception as e:
                        conn.rollback()
                        self.logger.error(f"Error executing query: {e}")
                        raise e
                    finally:
                        cursor.close()
            except sqlite3.OperationalError as e:
                self.__determine_retry(attempt=attempt, retries=retries, e=e)
                continue

    def _find_one(
        self, query: str, params: Optional[tuple] = None
    ) -> Optional[sqlite3.Row]:
        """
        Find one record using connection pool.

        Args:
            query (str): The query to be executed.
            params (tuple, optional):

        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql=query, parameters=params or ())
                return cursor.fetchone()
            finally:
                cursor.close()

    def _find_all(
        self, query: str, params: Optional[tuple] = None
    ) -> List[sqlite3.Row]:
        """
        Wrapper for execute select query function. Finds and returns all records.

        Args:
            query (str): The query to be executed.
            params (tuple, optional): The parameters to be passed to the query.

        Returns:
            List of all the database rows.
        """
        return self._execute_select_query(query=query, params=params)

    def _find_many(
        self, query: str, params: Optional[tuple] = None, limit: int = 100
    ) -> List[sqlite3.Row]:
        """
        Find many records with limit.

        Args:
            query (str): The query to be executed.
            params (tuple, optional): The parameters to be passed to the query.
            limit (int): The limit to be applied to the query.
        Returns:
            List of all the database rows.
        """
        limited_query = f"{query} LIMIT {limit}"
        return self._execute_select_query(limited_query, params)

    def __determine_retry(self, attempt: int, retries: int, e: str) -> None:
        if "database is locked" in str(e) and attempt < retries - 1:
            wait_time = 0.1 * (2**attempt)
            self.logger.warning(
                f"Database locked, retrying in {wait_time}s (attempt {attempt + 1}/{retries})"
            )
            time.sleep(wait_time)

    def begin_transaction(self):
        """Begin a database transaction."""
        self.connection.execute("BEGIN")
        self.logger.info("Transaction started")

    def commit_transaction(self):
        """Commit the current transaction."""
        self.connection.commit()
        self.logger.info("Transaction committed")

    def rollback_transaction(self):
        """Rollback the current transaction."""
        self.connection.rollback()
        self.logger.info("Transaction rolled back")
