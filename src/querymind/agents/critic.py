"""Deterministic critic guard (FR-8). LLM verdict never overrides empty evidence."""

from __future__ import annotations

from typing import Any

SUFFICIENT = "SUFFICIENT"
INSUFFICIENT = "INSUFFICIENT"


def evidence_is_usable(analyst_results: list[dict[str, Any]]) -> bool:
    """True when at least one sub-question returned a non-empty result set."""
    for item in analyst_results or []:
        if item.get("success") and item.get("result"):
            return True
    return False


def decide_verdict(
    analyst_results: list[dict[str, Any]],
    llm_verdict: str | None = None,
    reason: str = "",
) -> dict[str, str]:
    if not evidence_is_usable(analyst_results):
        return {
            "verdict": INSUFFICIENT,
            "reason": reason or "empty or failed evidence cannot be sufficient",
        }
    verdict = (llm_verdict or SUFFICIENT).upper()
    if verdict not in {SUFFICIENT, INSUFFICIENT}:
        verdict = INSUFFICIENT
        reason = reason or "invalid critic verdict"
    return {"verdict": verdict, "reason": reason or "evidence present"}
