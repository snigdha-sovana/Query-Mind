"""Investigation Manager: one sub-question by default; LLM can split later."""

from __future__ import annotations

from typing import Any, Callable


def make_plan(question: str, llm_caller: Callable[[str], str] | None = None, data_profile: str | None = None) -> list[str]:
    if not question.strip():
        return []
    if llm_caller is None:
        return [question]
    profile_text = f"\n\nData Profile:\n{data_profile}\n" if data_profile else ""
    prompt = (
        "Split this business question into independent SQL sub-questions, one per line. "
        "Do not include numbering, bullets, or explanations. "
        "If it is already a single question, repeat it once."
        f"{profile_text}\n\n"
        f"Question: {question}"
    )
    raw = llm_caller(prompt)
    lines = []
    for line in raw.splitlines():
        cleaned = line.strip(" -*\t1234567890.")
        if cleaned:
            lines.append(cleaned)
    return lines or [question]


def revise_plan(previous: list[str], critic_reason: str, llm_caller: Callable[[str], str] | None = None) -> list[str]:
    seed = previous[0] if previous else "the original question"
    reason = critic_reason or "insufficient evidence"
    if llm_caller is not None:
        prompt = (
            f"The previous query plan failed or yielded insufficient evidence for reason: '{reason}'.\n"
            f"Original Sub-questions: {previous}\n\n"
            "Propose a revised, simplified single SQL sub-question that addresses this issue. "
            "Return ONLY the single revised question."
        )
        try:
            revised_q = llm_caller(prompt).strip(" -*\t1234567890.")
            if revised_q:
                return [revised_q]
        except Exception:
            pass

    revised = [f"{seed} [revised: {reason}]"]
    if revised == previous:
        revised = [f"{seed} [retry]"]
    return revised
