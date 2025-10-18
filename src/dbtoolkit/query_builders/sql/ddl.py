from __future__ import annotations

from enum import Enum
from typing import List, Optional


class DDLQueryBuilder:
    @staticmethod
    def create(table: str, columns: List[tuple], primary_key_col: str) -> str:
        """
        Build create table query.

        Args:
            table (str): The desired table name.
            columns (List[tuple]): A list of column names and associated types.
            primary_key_col (str): The column name

        """
        if primary_key_col not in [col[0] for col in columns]:
            raise ValueError(
                "Primary key column must be one of the desired columns in the table!"
            )

        column_defs = []

        for col_name, col_type in columns:
            if col_name == primary_key_col:
                column_defs.append(f"{col_name} {col_type} PRIMARY KEY")
            else:
                column_defs.append(f"{col_name} {col_type}")

        columns_str = ", ".join(column_defs)

        return f"CREATE TABLE IF NOT EXISTS {table} ({columns_str})"

    @staticmethod
    def alter(
        table: str,
        operation: AlterTypes,
        column_def: Optional[str] = None,
        old_column: Optional[str] = None,
        new_column: Optional[str] = None,
    ):
        """
        Build alter table query.

        Args:
            table (str): The table to be altered.
            operation (str): The operation to be performed on the table (determined by enum).
            column_def (str, optional): Column definition for ADD operations (e.g., "age INTEGER")
            old_column (str, optional): Old column name for RENAME_COLUMN
            new_column (str, optional): New column name or table name for RENAME operations

        Returns:
            str: The ALTER TABLE SQL query
        """
        if operation == AlterTypes.ADD:
            if not column_def:
                raise ValueError("column_def required for ADD operation")
            return f"ALTER TABLE {table} ADD COLUMN {column_def}"

        elif operation == AlterTypes.DROP:
            if not old_column:
                raise ValueError("old_column required for DROP operation")
            return f"ALTER TABLE {table} DROP COLUMN {old_column}"

        elif operation == AlterTypes.RENAME_COLUMN:
            if not old_column or not new_column:
                raise ValueError(
                    "Both old_column and new_column required for RENAME_COLUMN"
                )
            return f"ALTER TABLE {table} RENAME COLUMN {old_column} TO {new_column}"

        elif operation == AlterTypes.RENAME_TABLE:
            if not new_column:
                raise ValueError(
                    "new_column (new table name) required for RENAME_TABLE"
                )
            return f"ALTER TABLE {table} RENAME TO {new_column}"

        else:
            raise ValueError(f"Unsupported ALTER operation: {operation}")

    @staticmethod
    def drop_table(table: str) -> str:
        """Build drop table query."""
        return f"DROP TABLE IF EXISTS {table}"


class AlterTypes(Enum):
    ADD = "ADD"
    DROP = "DROP"
    RENAME_COLUMN = "RENAME_COLUMN"
    RENAME_TABLE = "RENAME_TABLE"
