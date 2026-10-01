import pytest

from querymind.eval.harness import run_eval
from querymind.eval.e2e_harness import run_e2e_eval
from querymind.eval.ablation import run_ablation
from querymind.eval.metrics import execution_match, schema_recall
from querymind.eval.paths import find_questions_file


def test_execution_match_is_order_insensitive():
    left = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    right = [{"a": 3, "b": 4}, {"a": 1, "b": 2}]
    assert execution_match(left, right)
    assert not execution_match(left, [{"a": 1, "b": 9}])


def test_schema_recall_from_gold_sql():
    assert schema_recall(["sales", "customers"], "SELECT * FROM sales JOIN customers") == 1.0
    assert schema_recall(["sales"], "SELECT * FROM sales JOIN customers") == 0.5


def test_eval_harness_gold_smoke():
    try:
        find_questions_file()
    except FileNotFoundError:
        pytest.skip("Mini-Dev files are not available")
    report = run_eval(limit=2, db_id="student_club", use_gold_sql=True)
    assert report["summary"]["n"] == 2
    assert report["summary"]["gold_exec_failures"] == 0
    assert report["summary"]["execution_accuracy"] == 1.0


def test_eval_e2e_harness_gold_smoke():
    try:
        find_questions_file()
    except FileNotFoundError:
        pytest.skip("Mini-Dev files are not available")
    report = run_e2e_eval(limit=2, db_id="student_club", use_gold_sql=True)
    assert report["summary"]["n"] == 2
    assert report["summary"]["gold_exec_failures"] == 0
    assert report["summary"]["e2e_accuracy"] == 1.0


def test_ablation_gold_smoke():
    try:
        find_questions_file()
    except FileNotFoundError:
        pytest.skip("Mini-Dev files are not available")
    report = run_ablation(limit=2, db_id="student_club", use_gold_sql=True)
    assert report["ablation_summary"]["baseline_engine_accuracy"] == 1.0
    assert report["ablation_summary"]["full_graph_accuracy"] == 1.0

