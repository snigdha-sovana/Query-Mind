"""Parse table names from SQL for schema-linking recall."""

from __future__ import annotations

import re

_STRINGS = re.compile(r"('([^']|'')*'|\"([^\"]|\"\")*\")")
_TABLE_AFTER = re.compile(
    r"\b(?:from|join|update|into|table)\s+([a-zA-Z_][\w.]*)",
    re.IGNORECASE,
)


def extract_tables(sql: str) -> list[str]:
    cleaned = _STRINGS.sub("''", sql or "")
    names: list[str] = []
    seen: set[str] = set()
    for match in _TABLE_AFTER.finditer(cleaned):
        raw = match.group(1)
        name = raw.split(".")[-1]
        key = name.lower()
        if key.startswith("sqlite") or key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def strip_sql_fences(text: str) -> str:
    sql = (text or "").strip()
    if sql.startswith("```"):
        sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*```$", "", sql)
    return sql.strip().rstrip(";") + ";" if sql.strip() else ""
