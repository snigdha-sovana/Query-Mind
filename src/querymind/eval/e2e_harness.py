"""E2E Eval harness (FR-12). Evaluates full multi-agent investigation."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

from langgraph.checkpoint.memory import MemorySaver

from querymind.engine.db import DBExecutor
from querymind.engine.schema import SchemaLinker
from querymind.engine.sql_gen import SQLEngine
from querymind.eval.metrics import execution_match
from querymind.eval.paths import find_database, find_description_dir, load_questions
from querymind.graph.builder import build_graph


def evaluate_record_e2e(
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
            "e2e_correct": False,
        }

    linker = SchemaLinker(db_path, description_dir=desc_dir)

    if use_gold_sql or llm_caller is None:
        pred_ok = True
        correct = True
        final_verdict = "SUFFICIENT"
    else:
        engine = SQLEngine(db_path, llm_caller=llm_caller, schema_linker=linker, db_executor=executor)
        graph = build_graph(engine=engine, llm_caller=llm_caller, checkpointer=MemorySaver())
        thread_id = str(record.get("question_id") or uuid.uuid4())
        thread_config = {"configurable": {"thread_id": thread_id}}
        
        # Run graph
        for _ in graph.stream({"question": record["question"]}, thread_config):
            pass
            
        # Resume through any HITL interrupts
        while True:
            current_state = graph.get_state(thread_config)
            if not current_state.next:
                break
            for _ in graph.stream(None, thread_config):
                pass
                
        final_state = graph.get_state(thread_config).values
        analyst_results = final_state.get("analyst_results", [])
        
        # We consider E2E correct if ANY sub-question produced the exact gold result set.
        correct = False
        for res in analyst_results:
            if res.get("success") and execution_match(res.get("result", []), gold_rows):
                correct = True
                break
                
        final_verdict = final_state.get("verdict", "")
        pred_ok = len(analyst_results) > 0

    return {
        "question_id": record.get("question_id"),
        "db_id": db_id,
        "question": record["question"],
        "success": pred_ok,
        "e2e_correct": correct,
        "final_verdict": final_verdict,
        "gold_executed": True,
    }


def summarize_e2e(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows) or 1
    return {
        "n": len(rows),
        "e2e_accuracy": sum(1 for r in rows if r.get("e2e_correct")) / n,
        "gold_exec_failures": sum(1 for r in rows if not r.get("gold_executed")),
    }


def run_e2e_eval(
    limit: int | None = None,
    db_id: str | None = None,
    use_gold_sql: bool = False,
    llm_caller: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    records = load_questions(limit=limit, db_id=db_id)
    results = [
        evaluate_record_e2e(record, llm_caller=llm_caller, use_gold_sql=use_gold_sql)
        for record in records
    ]
    return {"summary": summarize_e2e(results), "results": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QueryMind E2E Eval harness")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--db-id", dest="db_id", default=None)
    parser.add_argument(
        "--gold",
        action="store_true",
        help="Skip LLM execution and assume perfect success.",
    )
    parser.add_argument("--out", default=None, help="Write JSON report to this path.")
    args = parser.parse_args(argv)

    llm_caller = None
    if not args.gold:
        from querymind.llm.client import get_llm_caller
        try:
            llm_caller = get_llm_caller()
        except RuntimeError as e:
            print(f"Error: {e}")
            return 1

    report = run_e2e_eval(limit=args.limit, db_id=args.db_id, use_gold_sql=args.gold, llm_caller=llm_caller)
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
