"""LangGraph investigation loop: Manager → Analyst → Critic → Report."""

from __future__ import annotations

from typing import Any, Callable, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from querymind.agents.critic import SUFFICIENT, decide_verdict
from querymind.agents.manager import make_plan, revise_plan
from querymind.agents.report import grounded_report
from querymind.config import MAX_INVESTIGATION_ITERS
from querymind.engine.sql_gen import SQLEngine
from querymind.graph.state import InvestigationState


def build_graph(
    engine: SQLEngine,
    llm_caller: Callable[[str], str] | None = None,
    max_iterations: int | None = None,
    checkpointer: Any = False,
    interrupt_before: list[str] | None = None,
):
    cap = MAX_INVESTIGATION_ITERS if max_iterations is None else max_iterations

    def profiler(state: InvestigationState) -> dict[str, Any]:
        iteration = int(state.get("iteration") or 0)
        if iteration > 0:
            return {}  # Only profile on first iteration
            
        linked = engine.schema_linker.link(state["question"]).tables
        if not linked:
            return {"data_profile": "No tables found."}
            
        profile_lines = []
        for table in linked:
            success, rows = engine.db_executor.execute(f"SELECT COUNT(*) as c FROM {table}")
            if success and rows:
                profile_lines.append(f"- Table `{table}` has {rows[0]['c']} rows.")
            else:
                profile_lines.append(f"- Table `{table}`: could not get count.")
                
        return {"data_profile": "\n".join(profile_lines)}

    def manager(state: InvestigationState) -> dict[str, Any]:
        iteration = int(state.get("iteration") or 0)
        previous = list(state.get("plan") or [])
        if iteration == 0:
            plan = make_plan(state["question"], llm_caller=llm_caller, data_profile=state.get("data_profile"))
        else:
            plan = revise_plan(previous, state.get("verdict_reason") or "", llm_caller=llm_caller)
        return {"plan": plan, "iteration": iteration + 1, "max_iterations": cap}

    def analyst(state: InvestigationState) -> dict[str, Any]:
        results = []
        for sub_q in state.get("plan") or [state["question"]]:
            outcome = engine.run_investigation(
                sub_q,
                evidence=state.get("evidence_hint") or "",
            )
            outcome["subquestion"] = sub_q
            results.append(outcome)
        return {"analyst_results": results}

    def critic(state: InvestigationState) -> dict[str, Any]:
        decision = decide_verdict(state.get("analyst_results") or [])
        return {"verdict": decision["verdict"], "verdict_reason": decision["reason"]}

    def report(state: InvestigationState) -> dict[str, Any]:
        return {"report": grounded_report(state["question"], state.get("analyst_results") or [], llm_caller=llm_caller)}

    def route(state: InvestigationState) -> Literal["manager", "report"]:
        if state.get("verdict") == SUFFICIENT:
            return "report"
        if int(state.get("iteration") or 0) >= int(state.get("max_iterations") or cap):
            return "report"
        return "manager"

    graph = StateGraph(InvestigationState)
    graph.add_node("profiler", profiler)
    graph.add_node("manager", manager)
    graph.add_node("analyst", analyst)
    graph.add_node("critic", critic)
    graph.add_node("report", report)
    graph.add_edge(START, "profiler")
    graph.add_edge("profiler", "manager")
    graph.add_edge("manager", "analyst")
    graph.add_edge("analyst", "critic")
    graph.add_conditional_edges("critic", route, {"manager": "manager", "report": "report"})
    compile_kwargs: dict[str, Any] = {}
    if checkpointer:
        compile_kwargs["checkpointer"] = checkpointer
    if interrupt_before:
        compile_kwargs["interrupt_before"] = interrupt_before
    return graph.compile(**compile_kwargs)
