"""Read-only SQLite execution with timeout and row limits."""

from __future__ import annotations

import os
import sqlite3
import time
from typing import Any

from querymind.config import QUERY_TIMEOUT_S, ROW_LIMIT
from querymind.engine.sql_safety import reject_if_unsafe


def sqlite_uri(db_path: str) -> str:
    abs_path = os.path.abspath(db_path).replace("\\", "/")
    if ":" in abs_path:
        return f"file:///{abs_path}?mode=ro"
    return f"file:{abs_path}?mode=ro"


from abc import ABC, abstractmethod


class BaseDBExecutor(ABC):
    @abstractmethod
    def execute(self, query: str) -> tuple[bool, Any]:
        """Execute query in read-only mode returning (success, result_rows_or_error)."""
        pass


class DBExecutor(BaseDBExecutor):
    def __init__(
        self,
        db_path: str,
        row_limit: int | None = None,
        timeout_s: float | None = None,
    ):
        self.db_path = os.path.abspath(db_path).replace("\\", "/")
        self.row_limit = ROW_LIMIT if row_limit is None else row_limit
        self.timeout_s = QUERY_TIMEOUT_S if timeout_s is None else timeout_s

    def execute(self, query: str) -> tuple[bool, Any]:
        """
        Execute SQL in read-only mode.
        Returns (success, result_rows_or_error_string).
        """
        unsafe = reject_if_unsafe(query)
        if unsafe:
            return False, unsafe

        conn = None
        try:
            conn = sqlite3.connect(sqlite_uri(self.db_path), uri=True, timeout=self.timeout_s)
            conn.row_factory = sqlite3.Row
            started = time.monotonic()

            def _progress() -> int:
                if time.monotonic() - started > self.timeout_s:
                    return 1
                return 0

            conn.set_progress_handler(_progress, 1000)
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchmany(self.row_limit)
            result = [dict(row) for row in rows]
            return True, result
        except sqlite3.OperationalError as exc:
            message = str(exc)
            if "interrupted" in message.lower():
                return False, f"Query exceeded timeout of {self.timeout_s}s"
            return False, message
        except sqlite3.Error as exc:
            return False, str(exc)
        except Exception as exc:  # noqa: BLE001 — structured error for the repair loop
            return False, str(exc)
        finally:
            if conn is not None:
                conn.close()


SQLiteExecutor = DBExecutor
