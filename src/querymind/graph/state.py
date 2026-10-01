"""Shared investigation state."""

from __future__ import annotations

from typing import Any, TypedDict


class InvestigationState(TypedDict, total=False):
    question: str
    data_profile: str
    evidence_hint: str
    db_path: str
    plan: list[str]
    analyst_results: list[dict[str, Any]]
    verdict: str
    verdict_reason: str
    report: str
    iteration: int
    max_iterations: int
