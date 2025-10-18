from __future__ import annotations

import pathlib
import queue
import sqlite3
import threading
from contextlib import contextmanager
from enum import Enum
from typing import Optional

from utils.utils import Utils


class DBConnection:
    def __init__(
        self,
        file_system: pathlib.Path = pathlib.Path("../scheduler/database/database.db"),
        in_memory: bool = False,
        timeout: float = 3600.0,
        isolation_level: Optional[IsolationLevels] = None,
        check_same_thread: bool = False,
        pool_size: int = 5,
    ) -> None:
        """Initializes a SQLite3 database connection pool."""
        self.file_system = file_system
        self.in_memory = in_memory
        self.timeout = timeout
        self.isolation_level = isolation_level
        self.check_same_thread = check_same_thread
        self.pool_size = pool_size
        self.connection_pool = queue.Queue(maxsize=pool_size)
        self.pool_lock = threading.Lock()
        self._initialize_pool()

        self.connection = self.__create_engine_conn(
            file_system=file_system,
            in_memory=in_memory,
            timeout=timeout,
            isolation_level=isolation_level,
            check_same_thread=check_same_thread,
        )
        self.logger = Utils.__set_logger()

    def _initialize_pool(self):
        """Initialize the connection pool with multiple connections."""
        for i in range(self.pool_size):
            conn = self.__create_engine_conn(
                file_system=self.file_system,
                in_memory=self.in_memory,
                timeout=self.timeout,
                isolation_level=self.isolation_level,
                check_same_thread=self.check_same_thread,
            )
            self.connection_pool.put(conn)
            self.logger.info(f"Created connection {i + 1}/{self.pool_size} for pool")

    def __create_engine_conn(
        self,
        file_system: pathlib.Path,
        in_memory: bool,
        timeout: float,
        isolation_level: str,
        check_same_thread: bool,
    ) -> sqlite3.Connection:
        """
        Creates the connection to the SQLite3 database engine.

        Args:
            file_system (pathlib.Path): Path to the SQLite database file. Ignored if in_memory=True.
            in_memory (bool): If True, creates an in-memory database (faster but not persistent).
            timeout (float): How long to wait for database locks before timing out (seconds).
                Default 3600 seconds (1 hour). Use shorter values for web apps.
            isolation_level: Controls when transactions are started:
                - None: Autocommit mode (no transactions, each statement commits immediately).
                - DEFERRED: Transaction starts when first write operation occurs.
                - IMMEDIATE: Transaction starts immediately, gets immediate lock.
                - EXCLUSIVE: Transaction starts immediately, gets exclusive lock.
            check_same_thread: If True, only the thread that created the connection
                can use it. Set to False for multi-threaded applications.

        Returns:
            sqlite3.Connection: A connection to the SQLite3 database.

        Raises:
            sqlite3.DatabaseError: If there's an error in establishing the DB connection.
        """

        try:
            if in_memory:
                database_path = ":memory:"
            else:
                database_path = str(file_system)
                file_system.parent.mkdir(parents=True, exist_ok=True)

            isolation_value = isolation_level.value if isolation_level else None

            connection = sqlite3.connect(
                database=database_path,
                timeout=timeout,
                isolation_level=isolation_value,
                check_same_thread=check_same_thread,
            )

            """
            Enable foreign key constraints and write-ahead logging, better for concurrency.
            
            Set larger cache and store temp tables in memory.
            """
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.execute("PRAGMA cache_size = 10000")
            connection.execute("PRAGMA temp_store = MEMORY")
            connection.execute("PRAGMA mmap_size = 268435456")

            connection.row_factory = sqlite3.Row

            return connection
        except sqlite3.DatabaseError as e:
            self.logger.error(
                f"There was an error connecting to the SQLite database: {e}"
            )
            raise e

    @contextmanager
    def get_connection(self):
        """
        Context manager for getting and returning connections from the pool.

        Usage:
            with db_manager.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM tasks")
                results = cursor.fetchall()
        """
        conn = None
        try:
            conn = self.connection_pool.get(timeout=self.timeout)
            self.logger.debug("Retrieved connection from pool")
            yield conn
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise e
        finally:
            if conn:
                self.connection_pool.put(conn)
                self.logger.debug("Returned connection to pool")

    def __close_pool(self):
        """Close all connections in the pool."""
        closed_count = 0
        while not self.connection_pool.empty():
            try:
                conn = self.connection_pool.get_nowait()
                conn.close()
                closed_count += 1
            except queue.Empty:
                break
        self.logger.info(f"Closed {closed_count} connections from pool.")

    def close(self):
        self.__close_pool()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures connection is closed."""
        self.close()


class IsolationLevels(Enum):
    DEFERRED = "DEFERRED"
    EXCLUSIVE = "EXCLUSIVE"
    IMMEDIATE = "IMMEDIATE"
