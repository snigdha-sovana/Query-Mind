"""F2 SQL generation and F3 execute/repair loop."""

from __future__ import annotations

from typing import Any, Callable

from querymind.config import MAX_SQL_RETRIES
from querymind.engine.db import DBExecutor
from querymind.engine.schema import LinkedSchema, SchemaLinker
from querymind.engine.sql_parse import strip_sql_fences


class SQLEngine:
    def __init__(
        self,
        db_path: str,
        llm_caller: Callable[[str], str],
        schema_linker: SchemaLinker | None = None,
        db_executor: DBExecutor | None = None,
    ):
        self.db_executor = db_executor or DBExecutor(db_path)
        self.schema_linker = schema_linker or SchemaLinker(db_path)
        self.llm_caller = llm_caller

    def generate_sql(
        self,
        question: str,
        schema: str,
        error_context: str = "",
        evidence: str = "",
    ) -> str:
        prompt = (
            "You are an expert SQLite analyst.\n"
            "Given the following database schema:\n"
            f"{schema}\n\n"
        )
        if evidence:
            prompt += f"External knowledge / evidence:\n{evidence}\n\n"
        prompt += f'Write a SQLite query to answer this question: "{question}"\n'
        if error_context:
            prompt += (
                f"\nYour previous query failed with this error:\n{error_context}\n"
                "Please fix the query.\n"
            )
        prompt += "\nReturn ONLY the SQL query. No markdown formatting, no explanation."
        return strip_sql_fences(self.llm_caller(prompt))

    def run_investigation(
        self,
        question: str,
        max_retries: int | None = None,
        evidence: str = "",
    ) -> dict[str, Any]:
        retries = MAX_SQL_RETRIES if max_retries is None else max_retries
        linked: LinkedSchema = self.schema_linker.link(question)
        schema = linked.schema_text
        error_context = ""
        last_sql = ""

        for attempt in range(retries + 1):
            sql = self.generate_sql(question, schema, error_context, evidence=evidence)
            last_sql = sql
            success, result = self.db_executor.execute(sql)
            if success:
                return {
                    "success": True,
                    "sql": sql,
                    "result": result,
                    "attempts": attempt + 1,
                    "linked_tables": linked.tables,
                    "repaired": attempt > 0,
                }
            error_context = str(result)

        return {
            "success": False,
            "sql": last_sql,
            "error": error_context,
            "attempts": retries + 1,
            "linked_tables": linked.tables,
            "repaired": retries > 0,
            "result": [],
        }
