"""Database catalog: tables, columns, optional description CSVs."""

from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from querymind.engine.db import sqlite_uri


@dataclass
class ColumnInfo:
    name: str
    declared_type: str = ""
    description: str = ""
    value_description: str = ""


@dataclass
class TableInfo:
    name: str
    sql: str = ""
    description: str = ""
    columns: list[ColumnInfo] = field(default_factory=list)

    def text_blob(self) -> str:
        parts = [self.name, self.description]
        for col in self.columns:
            parts.extend([col.name, col.declared_type, col.description, col.value_description])
        return " ".join(p for p in parts if p)


@dataclass
class SchemaCatalog:
    tables: dict[str, TableInfo]

    def table_names(self) -> list[str]:
        return list(self.tables.keys())

    def render(self, table_names: list[str] | None = None) -> str:
        names = table_names or self.table_names()
        blocks = []
        for name in names:
            table = self.tables.get(name)
            if table is None:
                continue
            lines = [f"TABLE {table.name}"]
            if table.description:
                lines.append(f"  description: {table.description}")
            if table.sql:
                lines.append(f"  ddl: {table.sql}")
            for col in table.columns:
                extra = []
                if col.description:
                    extra.append(col.description)
                if col.value_description:
                    extra.append(f"values: {col.value_description}")
                suffix = f" -- {' | '.join(extra)}" if extra else ""
                lines.append(f"  - {col.name} {col.declared_type}{suffix}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)


def load_catalog(
    db_path: str,
    description_dir: str | Path | None = None,
    description_json: str | Path | None = None,
) -> SchemaCatalog:
    tables = _tables_from_sqlite(db_path)
    if description_dir:
        _apply_csv_descriptions(tables, Path(description_dir))
    if description_json:
        _apply_json_descriptions(tables, Path(description_json))
    return SchemaCatalog(tables=tables)


def _tables_from_sqlite(db_path: str) -> dict[str, TableInfo]:
    conn = sqlite3.connect(sqlite_uri(db_path), uri=True)
    conn.row_factory = sqlite3.Row
    try:
        masters = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        tables: dict[str, TableInfo] = {}
        for row in masters:
            name = row["name"]
            info = TableInfo(name=name, sql=row["sql"] or "")
            pragma = conn.execute(f'PRAGMA table_info("{name}")').fetchall()
            for col in pragma:
                info.columns.append(
                    ColumnInfo(name=col["name"], declared_type=col["type"] or "")
                )
            tables[name] = info
        return tables
    finally:
        conn.close()


def _apply_csv_descriptions(tables: dict[str, TableInfo], directory: Path) -> None:
    if not directory.exists():
        return
    for csv_path in directory.glob("*.csv"):
        table_name = _match_table_name(csv_path.stem, tables)
        if table_name is None:
            continue
        table = tables[table_name]
        with csv_path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                original = (row.get("original_column_name") or row.get("column_name") or "").strip()
                if not original:
                    continue
                col = _find_column(table, original)
                if col is None:
                    continue
                col.description = (row.get("column_description") or row.get("column_name") or "").strip()
                col.value_description = (row.get("value_description") or "").strip()
                if not table.description and row.get("column_description"):
                    table.description = table.name.replace("_", " ")


def _apply_json_descriptions(tables: dict[str, TableInfo], path: Path) -> None:
    if not path.exists():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    for table_name, spec in payload.items():
        table = tables.get(table_name)
        if table is None:
            continue
        table.description = spec.get("table", table.description)
        for col_name, desc in spec.get("columns", {}).items():
            col = _find_column(table, col_name)
            if col is not None:
                col.description = desc


def _match_table_name(stem: str, tables: dict[str, TableInfo]) -> str | None:
    lowered = {name.lower(): name for name in tables}
    if stem.lower() in lowered:
        return lowered[stem.lower()]
    collapsed = stem.lower().replace("_", "").replace(" ", "")
    for name in tables:
        if name.lower().replace("_", "") == collapsed:
            return name
    return None


def _find_column(table: TableInfo, name: str) -> ColumnInfo | None:
    lowered = name.lower()
    for col in table.columns:
        if col.name.lower() == lowered:
            return col
    return None
