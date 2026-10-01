import json
from pathlib import Path

import pytest

from querymind.engine.db import DBExecutor
from querymind.engine.schema import SchemaLinker
from querymind.engine.sql_gen import SQLEngine
from querymind.engine.sql_parse import extract_tables
from querymind.llm.client import LLMClient

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE_DB = FIXTURES / "fixture.sqlite"
DESC_JSON = FIXTURES / "schema_descriptions.json"
QUESTIONS = json.loads((FIXTURES / "fixture_questions.json").read_text(encoding="utf-8"))



def test_db_executor_valid_sql():
    executor = DBExecutor(str(FIXTURE_DB))
    success, result = executor.execute("SELECT * FROM sales;")
    assert success
    assert len(result) == 2
    assert result[0]["amount"] == 100.5


def test_db_executor_invalid_sql():
    executor = DBExecutor(str(FIXTURE_DB))
    success, result = executor.execute("SELECT * FROM non_existent_table;")
    assert success is False
    assert "no such table" in result


def test_db_executor_read_only():
    executor = DBExecutor(str(FIXTURE_DB))
    success, result = executor.execute("INSERT INTO sales VALUES (3, 1, 300.0);")
    assert success is False
    assert "read-only" in result.lower() or "not allowed" in result.lower()


def test_db_executor_row_limit():
    executor = DBExecutor(str(FIXTURE_DB), row_limit=1)
    success, result = executor.execute("SELECT * FROM sales;")
    assert success
    assert len(result) == 1


def test_db_executor_timeout():
    executor = DBExecutor(str(FIXTURE_DB), timeout_s=0.05)
    sql = """
    WITH RECURSIVE t(x) AS (
        SELECT 1
        UNION ALL
        SELECT x + 1 FROM t WHERE x < 100000000
    )
    SELECT count(x) FROM t;
    """
    success, result = executor.execute(sql)
    assert success is False
    assert "timeout" in result.lower() or "interrupted" in result.lower()


def test_sql_engine_success():
    def mock_llm(prompt: str) -> str:
        return "SELECT SUM(amount) AS total FROM sales;"

    engine = SQLEngine(str(FIXTURE_DB), llm_caller=mock_llm)
    res = engine.run_investigation("What is the total revenue?")
    assert res["success"]
    assert res["attempts"] == 1
    assert res["result"][0]["total"] == 300.5


def test_sql_engine_repair_loop():
    call_count = {"count": 0}

    def mock_llm(prompt: str) -> str:
        call_count["count"] += 1
        if call_count["count"] == 1:
            return "SELECT SUM(amount) AS total FROM non_existent_table;"
        return "SELECT SUM(amount) AS total FROM sales;"

    engine = SQLEngine(str(FIXTURE_DB), llm_caller=mock_llm)
    res = engine.run_investigation("What is the total revenue?", max_retries=3)
    assert res["success"]
    assert res["attempts"] == 2
    assert res["repaired"] is True
    assert res["result"][0]["total"] == 300.5


def test_sql_engine_repair_cap():
    def mock_llm(prompt: str) -> str:
        return "SELECT * FROM missing;"

    engine = SQLEngine(str(FIXTURE_DB), llm_caller=mock_llm)
    res = engine.run_investigation("What is the total revenue?", max_retries=2)
    assert res["success"] is False
    assert res["attempts"] == 3


def test_schema_linker_recall():
    linker = SchemaLinker(str(FIXTURE_DB), description_json=DESC_JSON, top_k=2)
    for item in QUESTIONS:
        recall = linker.recall(item["question"], item["gold_tables"])
        assert recall == 1.0, item["question"]
        linked = linker.link(item["question"]).tables
        assert item["gold_tables"][0] in linked


def test_extract_tables_from_gold_sql():
    sql = "SELECT T1.name FROM customers AS T1 JOIN sales AS T2 ON T1.id = T2.customer_id"
    assert extract_tables(sql) == ["customers", "sales"]


def test_llm_client_retries_on_429():
    calls = {"n": 0}

    client = LLMClient.__new__(LLMClient)
    client.max_retries = 3

    def flaky(prompt: str) -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("HTTP 429 rate limit")
        return "ok"

    client._invoke = flaky
    assert client("hello_flaky_test") == "ok"
    assert calls["n"] == 3


def test_llm_client_caching():
    calls = {"n": 0}

    client = LLMClient.__new__(LLMClient)
    client.max_retries = 3

    def fake_invoke(prompt: str) -> str:
        calls["n"] += 1
        return f"response for {prompt}"

    client._invoke = fake_invoke
    
    # Clean up cache file before test if exists
    from pathlib import Path
    cache_path = Path(".llm_cache.sqlite")
    if cache_path.exists():
        cache_path.unlink()

    res1 = client("hello cache")
    assert res1 == "response for hello cache"
    assert calls["n"] == 1

    res2 = client("hello cache")
    assert res2 == "response for hello cache"
    assert calls["n"] == 1  # Hit cache

