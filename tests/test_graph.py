from pathlib import Path

from querymind.engine.sql_gen import SQLEngine
from querymind.graph.builder import build_graph

FIXTURE_DB = Path(__file__).parent / "fixtures" / "fixture.sqlite"


def test_investigation_cycle_insufficient_then_sufficient():
    calls = {"n": 0}

    def mock_llm(prompt: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return "SELECT amount FROM sales WHERE amount < 0;"
        return "SELECT SUM(amount) AS total FROM sales;"

    engine = SQLEngine(str(FIXTURE_DB), llm_caller=mock_llm)
    app = build_graph(engine, max_iterations=3)
    state = app.invoke({"question": "What is the total revenue?"})

    assert state["verdict"] == "SUFFICIENT"
    assert state["iteration"] == 2
    assert "300.5" in state["report"]
    assert state["analyst_results"][-1]["success"]


def test_max_iterations_exits_to_report():
    def mock_llm(prompt: str) -> str:
        return "SELECT amount FROM sales WHERE amount < 0;"

    engine = SQLEngine(str(FIXTURE_DB), llm_caller=mock_llm)
    app = build_graph(engine, max_iterations=2)
    state = app.invoke({"question": "What is the total revenue?"})
    assert state["iteration"] == 2
    assert "report" in state
    assert state["verdict"] == "INSUFFICIENT"
