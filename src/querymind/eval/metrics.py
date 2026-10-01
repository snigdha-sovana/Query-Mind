"""Execution-accuracy and schema-linking recall."""

from __future__ import annotations

from collections import Counter
from typing import Any

from querymind.engine.sql_parse import extract_tables


def normalize_value(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, int):
        return value
    if value is None:
        return None
    text = str(value).strip()
    try:
        if "." in text:
            return round(float(text), 4)
        return int(text)
    except ValueError:
        return text


def result_bag(rows: list[Any]) -> Counter:
    bag: Counter = Counter()
    for row in rows or []:
        if isinstance(row, dict):
            cells = tuple(normalize_value(v) for v in row.values())
        else:
            cells = tuple(normalize_value(v) for v in row)
        bag[cells] += 1
    return bag


def execution_match(predicted: list[Any], gold: list[Any]) -> bool:
    return result_bag(predicted) == result_bag(gold)


def schema_recall(linked_tables: list[str], gold_sql: str) -> float:
    gold = {name.lower() for name in extract_tables(gold_sql)}
    if not gold:
        return 1.0
    linked = {name.lower() for name in linked_tables}
    return len(linked & gold) / len(gold)
