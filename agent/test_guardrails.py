"""가드레일 self-check. `uv run python test_guardrails.py`."""
import asyncio
from pathlib import Path

from guardrails.harness import guard, GuardViolation, load_spec
from guardrails.checks import pre_normalizer, post_normalizer, pre_planner, post_planner, pre_executor, post_executor, pre_reviewer, post_reviewer, pre_aggregator, post_aggregator, pre_compliance, post_compliance


async def test_harness():
    async def node(state):
        state["ran"] = True
        return state

    # post 이탈 없음 → 통과
    g = guard(node, "t", "x.md", post=lambda s: [])
    out = await g({})
    assert out["ran"] is True

    # post 이탈 + block → GuardViolation
    g = guard(node, "t", "x.md", post=lambda s: ["bad"])
    try:
        await g({})
        assert False, "should raise"
    except GuardViolation as e:
        assert e.node == "t" and e.problems == ["bad"]

    # log 모드 → raise 안 함
    g = guard(node, "t", "x.md", post=lambda s: ["bad"], on_violation="log")
    out = await g({})
    assert out["ran"] is True

    # pre 이탈 → 노드 실행 전 차단
    g = guard(node, "t", "x.md", pre=lambda s: ["pre-bad"])
    try:
        await g({})
        assert False
    except GuardViolation as e:
        assert e.problems == ["pre-bad"]

    # load_spec
    tmp = Path(__file__).resolve().parent / "guardrails"
    txt = load_spec("__missing__")
    assert txt == ""
    print("  harness OK")


def _norm_state(**over):
    nd = {"age": 30, "gender": "female", "gender_defaulted": False,
          "is_pii": {"name": True}, "name": "홍길동"}
    nd.update(over.get("nd", {}))
    s = {"user_input": {"x": 1}, "normalized_data": nd,
         "target_nutrients": ["vitamin_d"]}
    s.update(over.get("top", {}))
    return s


async def test_normalizer():
    assert pre_normalizer({"user_input": {}}) == []
    assert pre_normalizer({}) == ["user_input 없음"]
    assert post_normalizer(_norm_state()) == []
    assert post_normalizer(_norm_state(nd={"age": 17})), "age<19 flag"
    assert post_normalizer(_norm_state(nd={"gender": "x"})), "gender flag"
    assert post_normalizer(_norm_state(nd={"gender_defaulted": True})), "defaulted flag"
    assert post_normalizer(_norm_state(nd={"age_defaulted": True})), "age defaulted flag"
    assert post_normalizer(_norm_state(top={"target_nutrients": []})), "targets flag"
    print("  normalizer OK")


def _plan_ok():
    return [
        {"step": 1, "tool_name": "calculate_dynamic_ri",
         "args": {"age": 30, "gender": "female", "weight_kg": 60, "target_nutrients": ["vitamin_d"]}},
        {"step": 2, "tool_name": "search_products", "args": {"target_nutrients": ["vitamin_d"]}},
        {"step": 3, "tool_name": "check_nutrient_interactions", "args": {"nutrient_list": ["vitamin_d"]}},
        {"step": 4, "tool_name": "validate_ul_guardrail",
         "args": {"current_supps_intake": {}, "diet_estimated_intake": {}, "proposed_supps_intake": {},
                  "age": 30, "gender": "female", "weight_kg": 60}},
    ]


async def test_planner():
    assert pre_planner({"normalized_data": {}, "target_nutrients": []}) == []
    assert pre_planner({}), "missing precondition"
    assert post_planner({"execution_plan": _plan_ok()}) == []
    bad_tool = _plan_ok(); bad_tool[0]["tool_name"] = "nope"
    assert post_planner({"execution_plan": bad_tool}), "unknown tool flag"
    bad_arg = _plan_ok(); bad_arg[0]["args"].pop("gender")
    assert post_planner({"execution_plan": bad_arg}), "missing arg flag"
    bad_order = _plan_ok()
    bad_order[1]["step"], bad_order[3]["step"] = 4, 2  # search after ul
    assert post_planner({"execution_plan": bad_order}), "order flag"
    print("  planner OK")


def _exec_ok():
    return [
        {"task_name": "calculate_dynamic_ri", "status": "success",
         "result": {"custom_ri": {"vitamin_d": {"value": 10}}}},
        {"task_name": "search_products", "status": "success", "result": {"products": []}},
    ]


async def test_executor():
    assert pre_executor({"execution_plan": []}) == []
    assert pre_executor({}), "missing plan"
    assert post_executor({"execution_results": _exec_ok()}) == []
    assert post_executor({"execution_results": []}), "empty results"
    bad_status = _exec_ok(); bad_status[0]["status"] = "weird"
    assert post_executor({"execution_results": bad_status}), "status flag"
    leak = _exec_ok(); leak[0]["result"]["custom_ri"]["vitamin_d"]["value"] = 0
    assert post_executor({"execution_results": leak}), "0 leak flag"
    print("  executor OK")


async def test_reviewer_guard():
    assert pre_reviewer({"execution_results": []}) == []
    assert pre_reviewer({}), "missing results"
    assert post_reviewer({"review_status": "pass", "retry_count": 1}) == []
    assert post_reviewer({"review_status": "nonsense"}), "status flag"
    assert post_reviewer({"review_status": "pass", "retry_count": 99}), "retry flag"
    assert post_reviewer({"review_status": "pass",
                          "failed_items": [{"tool_name": "x"}]}), "failed_item shape flag"
    print("  reviewer_guard OK")


def _agg_state():
    results = [
        {"task_name": "calculate_dynamic_ri", "status": "success", "result": {"custom_ri": {"vitamin_d": {"value": 10}}}},
        {"task_name": "validate_ul_guardrail", "status": "success", "result": {"is_safe": True}},
    ]
    rep = {
        "title": "t", "user_profile": {},
        "guidelines": [{"text": "a", "source": "file.pdf p.1"}],
        "calculated_target": {"custom_ri": {"vitamin_d": {"value": 10}}},
        "ul_check": {"is_safe": True},
        "coverage": {}, "lab_results": {},
    }
    return {"execution_results": results, "aggregated_report": rep}


async def test_aggregator():
    assert pre_aggregator({"execution_results": []}) == []
    assert pre_aggregator({}), "missing results"
    assert post_aggregator(_agg_state()) == []
    s = _agg_state(); del s["aggregated_report"]["title"]
    assert post_aggregator(s), "missing key flag"
    s = _agg_state(); s["aggregated_report"]["calculated_target"] = {"custom_ri": {"vitamin_d": {"value": 999}}}
    assert post_aggregator(s), "pass-through mismatch flag"
    s = _agg_state(); s["aggregated_report"]["guidelines"] = [{"text": "a"}]
    assert post_aggregator(s), "guideline missing-source flag"
    print("  aggregator OK")


def _comp_state(html="<p>홍*동 리포트</p>", disc="…의료법상…"):
    return {
        "normalized_data": {"name": "홍길동", "birth_date": "1990-01-01"},
        "final_report": {"html": html, "disclaimer": disc,
                         "user_profile": {"name": "홍*동"}},
    }


async def test_compliance():
    assert pre_compliance({"aggregated_report": {}}) == []
    assert pre_compliance({}), "missing report"
    assert post_compliance(_comp_state()) == []
    assert post_compliance(_comp_state(html="")), "empty html flag"
    assert post_compliance(_comp_state(disc="없음")), "disclaimer flag"
    assert post_compliance(_comp_state(html="<p>홍길동 노출</p>")), "name leak flag"
    assert post_compliance(_comp_state(html="<p>주민 900101-1234567</p>")), "rrn flag"
    print("  compliance OK")


async def test_wired_graph():
    # 래핑된 그래프가 정상 입력에 대해 GuardViolation 없이 완주.
    from graph.workflow import graph
    st = await graph.ainvoke({
        "user_input": {"name": "홍길동", "age": 30, "gender": "female", "weight_kg": 60},
        "retry_count": 0,
    })
    assert "final_report" in st
    print("  wired_graph OK")


async def main():
    await test_harness()
    await test_normalizer()
    await test_planner()
    await test_executor()
    await test_reviewer_guard()
    await test_aggregator()
    await test_compliance()
    await test_wired_graph()
    print("ALL PASS")


if __name__ == "__main__":
    asyncio.run(main())
