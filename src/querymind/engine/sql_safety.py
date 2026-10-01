"""Guards for untrusted, model-generated SQL."""

from __future__ import annotations

import re

_WRITE_OR_DANGEROUS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "replace",
    "attach",
    "detach",
    "vacuum",
    "pragma",
    "grant",
    "revoke",
    "reindex",
}

_LEADING_COMMENT = re.compile(
    r"^(\s|--[^\n]*\n|/\*.*?\*/)*",
    re.DOTALL,
)
_FIRST_WORD = re.compile(r"([a-zA-Z_]+)")


def first_keyword(sql: str) -> str:
    stripped = _LEADING_COMMENT.sub("", sql or "").strip()
    match = _FIRST_WORD.match(stripped)
    return match.group(1).lower() if match else ""


def is_read_only_sql(sql: str) -> bool:
    keyword = first_keyword(sql)
    return keyword in {"select", "with", "explain"}


def reject_if_unsafe(sql: str) -> str | None:
    keyword = first_keyword(sql)
    if not keyword:
        return "Empty SQL statement is not allowed"
    if keyword in _WRITE_OR_DANGEROUS or keyword not in {"select", "with", "explain"}:
        return f"Only read-only SELECT/WITH queries are allowed (got {keyword!r})"
    return None
