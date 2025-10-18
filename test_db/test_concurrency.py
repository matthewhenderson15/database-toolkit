import sqlite3
import threading

from setup import Setup

from src.config import database


class TestConcurrency(Setup):
    def __init__(self):
        super().__init__()

    def test_concurrent_reads(self):
        """Test concurrent reads using threading library."""
        db_path = self.create_test_table()
        results = []
        errors = []

        def read_worker(worker_id: int):
            try:
                with database.DatabaseManager(
                    file_system=db_path, check_same_thread=False
                ) as manager:
                    rows = manager._find_all(query="SELECT COUNT(*) FROM test_users")
                    results.append((worker_id, rows[0][0]))
            except Exception as e:
                errors.append((worker_id, str(e)))

        threads = []

        for i in range(5):
            thread = threading.Thread(target=read_worker, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0, f"Errors occurred: {errors}."
        assert len(results) == 5, "All threads should successfully complete."

        counts = [result[1] for result in results]
        assert all(counts == 10 for count in counts), (
            "All threads should have the same data."
        )

    def test_concurrent_writes(self):
        """Test concurrent writes using threading library."""
        db_path = self.create_test_table()
        successful_writes = []
        errors = []

        def write_worker(worker_id: int):
            try:
                with database.DatabaseManager(
                    file_system=db_path, check_same_thread=False
                ) as manager:
                    insert_query = database.DMLQueryBuilder.insert(
                        columns=["id", "name", "created_at", "updated_at"],
                        table="test_users",
                    )
                    row_count = manager._execute(query=insert_query)
                    if successful_writes:
                        successful_writes.append((worker_id, row_count))
            except sqlite3.IntegrityError as e:
                errors.append((worker_id, "Integrity Error", str(e)))
            except Exception as e:
                errors.append((worker_id, "Unexpected Error", str(e)))

        threads = []

        for i in range(5):
            thread = threading.Thread(target=write_worker, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len([e for e in errors if e[1] == "UnexpectedError"]) == 0, (
            f"Unexpected errors: {errors}"
        )
        assert len(successful_writes) == 5, (
            "All threads should have successful writes to the test table."
        )

        with database.DatabaseManager(
            file_system=db_path, check_same_thread=False
        ) as manager:
            count = manager._find_all(query="SELECT COUNT(*) FROM test_users")
            assert len(count) == 15, f"Expected 15 records, got {count}"

    def test_locking_retry(self):
        """Test retry logic when database is locked."""
        pass

    # Thread safety and locking
