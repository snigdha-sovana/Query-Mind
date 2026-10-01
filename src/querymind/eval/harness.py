"""Eval harness for the SQL engine (FR-5). Live LLM calls are optional."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

from querymind.engine.db import DBExecutor
from querymind.engine.schema import SchemaLinker
from querymind.engine.sql_gen import SQLEngine
from querymind.eval.metrics import execution_match, schema_recall
from querymind.eval.paths import find_database, find_description_dir, load_questions


def evaluate_record(
    record: dict[str, Any],
    llm_caller: Callable[[str], str] | None,
    use_gold_sql: bool = False,
) -> dict[str, Any]:
    db_id = record["db_id"]
    db_path = str(find_database(db_id))
    desc_dir = find_description_dir(db_id)
    executor = DBExecutor(db_path)
    gold_sql = record.get("SQL") or record.get("gold_sql")
    gold_ok, gold_rows = executor.execute(gold_sql)
    if not gold_ok:
        return {
            "question_id": record.get("question_id"),
            "db_id": db_id,
            "gold_executed": False,
            "gold_error": gold_rows,
            "execution_correct": False,
            "schema_recall": 0.0,
            "repaired": False,
        }

    linker = SchemaLinker(db_path, description_dir=desc_dir)
    linked = linker.link(record["question"])

    if use_gold_sql or llm_caller is None:
        pred_sql = gold_sql
        pred_ok, pred_rows = True, gold_rows
        attempts = 1
        repaired = False
        success = True
    else:
        engine = SQLEngine(db_path, llm_caller=llm_caller, schema_linker=linker, db_executor=executor)
        outcome = engine.run_investigation(
            record["question"],
            evidence=record.get("evidence") or "",
        )
        pred_sql = outcome.get("sql")
        pred_ok = outcome["success"]
        pred_rows = outcome.get("result") or []
        attempts = outcome.get("attempts", 1)
        repaired = bool(outcome.get("repaired"))
        success = pred_ok
        linked.tables = outcome.get("linked_tables", linked.tables)

    correct = bool(pred_ok and execution_match(pred_rows, gold_rows))
    return {
        "question_id": record.get("question_id"),
        "db_id": db_id,
        "question": record["question"],
        "success": success,
        "execution_correct": correct,
        "schema_recall": schema_recall(linked.tables, gold_sql),
        "linked_tables": linked.tables,
        "attempts": attempts,
        "repaired": repaired,
        "pred_sql": pred_sql,
        "gold_sql": gold_sql,
        "gold_executed": True,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows) or 1
    return {
        "n": len(rows),
        "execution_accuracy": sum(1 for r in rows if r.get("execution_correct")) / n,
        "schema_linking_recall": sum(r.get("schema_recall") or 0.0 for r in rows) / n,
        "repair_rate": sum(1 for r in rows if r.get("repaired")) / n,
        "gold_exec_failures": sum(1 for r in rows if not r.get("gold_executed")),
    }


def run_eval(
    limit: int | None = None,
    db_id: str | None = None,
    use_gold_sql: bool = False,
    llm_caller: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    records = load_questions(limit=limit, db_id=db_id)
    results = [
        evaluate_record(record, llm_caller=llm_caller, use_gold_sql=use_gold_sql)
        for record in records
    ]
    return {"summary": summarize(results), "results": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QueryMind SQL eval harness")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--db-id", dest="db_id", default=None)
    parser.add_argument(
        "--gold",
        action="store_true",
        help="Execute gold SQL only (plumbing check, no LLM).",
    )
    parser.add_argument("--out", default=None, help="Write JSON report to this path.")
    args = parser.parse_args(argv)

    llm_caller = None
    if not args.gold:
        from querymind.llm.client import get_llm_caller

        llm_caller = get_llm_caller()

    report = run_eval(limit=args.limit, db_id=args.db_id, use_gold_sql=args.gold, llm_caller=llm_caller)
    text = json.dumps(report["summary"], indent=2)
    print(text)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
