from __future__ import annotations

from enum import Enum
from typing import List, Optional


class DMLQueryBuilder:
    @staticmethod
    def select(
        columns: List[str],
        table: str,
        where_clause: Optional[str],
        order_by_col: Optional[str],
        group_by_col: Optional[str],
        asc_desc: Optional[SQLQueryParams],
        limit: Optional[int] = None,
    ) -> str:
        columns_str = ", ".join(columns)
        query_parts = [f"SELECT {columns_str}", f"FROM {table}"]

        if where_clause:
            query_parts.append(f"WHERE {where_clause}")
        if group_by_col:
            query_parts.append(f"GROUP BY {group_by_col}")
        if order_by_col:
            direction = f"{asc_desc.value.upper()}" if asc_desc else ""
            query_parts.append(f"ORDER BY {order_by_col} {direction}")
        if limit:
            query_parts.append(f"LIMIT {limit}")

        return " ".join(query_parts)

    @staticmethod
    def insert(
        columns: List[str],
        table: str,
    ) -> str:
        """Build insert query."""
        columns_str = ", ".join(columns)
        placeholders = ", ".join(["?" for _ in columns])

        return f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"

    @staticmethod
    def update(
        table: str, columns: List[str], values: List[str], where_clause: str
    ) -> str:
        """Build update query"""
        if len(columns) != len(values):
            raise ValueError("Each column must have a corresponding update value!")

        set_clauses = [f"{col} = ?" for col in columns]
        set_str = ", ".join(set_clauses)

        return f"UPDATE {table} SET {set_str} WHERE {where_clause}"

    @staticmethod
    def delete(table: str, where_clause: str) -> str:
        """Build delete query."""
        return f"DELETE FROM {table} WHERE {where_clause}"


class SQLQueryParams(Enum):
    ASCENDING = "asc"
    DESCENDING = "desc"
