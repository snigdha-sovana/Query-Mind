"""Rebuild the hermetic fixture SQLite database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("fixture.sqlite")


def build(path: Path = DB_PATH) -> Path:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY,
                name TEXT,
                district TEXT
            );
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                name TEXT,
                stock INTEGER
            );
            CREATE TABLE sales (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                amount REAL
            );

            INSERT INTO customers (id, name, district) VALUES
                (1, 'Ada', 'North'),
                (2, 'Ben', 'South');
            INSERT INTO products (id, name, stock) VALUES
                (1, 'Widget', 10),
                (2, 'Gadget', 25);
            INSERT INTO sales (id, customer_id, amount) VALUES
                (1, 1, 100.5),
                (2, 2, 200.0);
            """
        )
        conn.commit()
    finally:
        conn.close()
    return path


if __name__ == "__main__":
    print(build())
