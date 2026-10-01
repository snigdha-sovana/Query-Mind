"""Trace logging utilities for PRD FR-14 compliance."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from querymind.config import ROOT

TRACE_DIR = ROOT / "logs" / "traces"


def save_run_trace(
    question: str,
    final_state: dict[str, Any],
    execution_time_s: float | None = None,
    trace_id: str | None = None,
) -> str:
    """Save a structured machine-readable run trace file for observability."""
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    tid = trace_id or f"run_{ts}"
    file_path = TRACE_DIR / f"trace_{ts}_{tid}.json"

    analyst_results = final_state.get("analyst_results", [])
    queries = [
        {
            "subquestion": item.get("subquestion"),
            "sql": item.get("sql"),
            "success": item.get("success"),
            "attempts": item.get("attempts"),
            "repaired": item.get("repaired"),
            "error": item.get("error"),
            "rows_returned": len(item.get("result") or []),
        }
        for item in analyst_results
    ]

    trace_data = {
        "trace_id": tid,
        "timestamp": ts,
        "question": question,
        "data_profile": final_state.get("data_profile"),
        "plan": final_state.get("plan"),
        "queries": queries,
        "verdict": final_state.get("verdict"),
        "verdict_reason": final_state.get("verdict_reason"),
        "iteration_count": final_state.get("iteration"),
        "max_iterations": final_state.get("max_iterations"),
        "report": final_state.get("report"),
        "execution_time_s": execution_time_s,
    }

    file_path.write_text(json.dumps(trace_data, indent=2), encoding="utf-8")
    return str(file_path)
