from querymind.agents.critic import INSUFFICIENT, SUFFICIENT, decide_verdict
from querymind.agents.manager import make_plan, revise_plan
from querymind.agents.report import assert_report_grounded, grounded_report


def test_critic_empty_evidence_never_sufficient():
    decision = decide_verdict([], llm_verdict=SUFFICIENT)
    assert decision["verdict"] == INSUFFICIENT

    decision = decide_verdict(
        [{"success": False, "result": [], "error": "boom"}],
        llm_verdict=SUFFICIENT,
    )
    assert decision["verdict"] == INSUFFICIENT

    decision = decide_verdict(
        [{"success": True, "result": []}],
        llm_verdict=SUFFICIENT,
    )
    assert decision["verdict"] == INSUFFICIENT


def test_critic_nonempty_can_be_sufficient():
    decision = decide_verdict(
        [{"success": True, "result": [{"total": 3}]}],
        llm_verdict=SUFFICIENT,
    )
    assert decision["verdict"] == SUFFICIENT


def test_report_grounding_rejects_unknown_numbers():
    evidence = [{"success": True, "sql": "SELECT 1", "result": [{"total": 300.5}]}]
    report = grounded_report("totals", evidence)
    assert assert_report_grounded(report, evidence)
    assert not assert_report_grounded(report + "\nsecret 9999", evidence)


def test_manager_plan_and_revise():
    plan = make_plan("Why did revenue drop?")
    assert plan == ["Why did revenue drop?"]
    revised = revise_plan(plan, "empty result")
    assert revised != plan
    assert revised
