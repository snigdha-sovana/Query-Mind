"""Locate BIRD Mini-Dev files without hard-coding a single layout."""

from __future__ import annotations

import json
from pathlib import Path

from querymind.config import BUNDLED_MINIDEV, DATA_DIR, ROOT


def candidate_roots() -> list[Path]:
    roots = [DATA_DIR, ROOT / "data", BUNDLED_MINIDEV]
    unique: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(root)
    return unique


def find_questions_file() -> Path:
    names = [
        "mini_dev_sqlite.json",
        "mini_dev.json",
    ]
    for root in candidate_roots():
        for name in names:
            path = root / name
            if path.exists():
                return path
    raise FileNotFoundError(
        "Could not find mini_dev_sqlite.json. Set QUERYMIND_DATA_DIR or keep the bundled Mini-Dev checkout."
    )


def find_database(db_id: str) -> Path:
    rels = [
        Path("dev_databases") / db_id / f"{db_id}.sqlite",
        Path("databases") / db_id / f"{db_id}.sqlite",
        Path(db_id) / f"{db_id}.sqlite",
    ]
    for root in candidate_roots():
        for rel in rels:
            path = root / rel
            if path.exists():
                return path
    raise FileNotFoundError(f"SQLite file for db_id={db_id!r} not found under {candidate_roots()}")


def find_description_dir(db_id: str) -> Path | None:
    db_file = find_database(db_id)
    desc = db_file.parent / "database_description"
    return desc if desc.exists() else None


def load_questions(limit: int | None = None, db_id: str | None = None) -> list[dict]:
    payload = json.loads(find_questions_file().read_text(encoding="utf-8"))
    records = payload
    if db_id:
        records = [row for row in records if row.get("db_id") == db_id]
    if limit is not None:
        records = records[:limit]
    return records
