"""핵심 로직 self-check. 프레임워크 없음. `uv run python test_pipeline.py`.

커버: Reviewer 재시도/부분실패 라우팅, Executor 배치 그룹핑+fallback+의존주입,
Compliance PII 마스킹, Planner 결정적 계획.
"""
import asyncio

from nodes.reviewer import specialized_review_node, MAX_RETRIES
from nodes.executor import executor_node, _batches
from nodes.compliance import _mask_name, _mask_birth, legal_compliance_node
from nodes.planner import _deterministic_plan


def _ul(is_safe):
    return {
        "task_name": "validate_ul_guardrail",
        "status": "success",
        "step": 4,
        "result": {"is_safe": is_safe, "ul_violations": []},
    }


async def test_reviewer():
    # 통과
    s = await specialized_review_node({"execution_results": [_ul(True)]})
    assert s["review_status"] == "pass", s

    # UL 위반, 재시도 여유 → planner 라우팅 + 카운트 증가
    s = await specialized_review_node(
        {"execution_results": [_ul(False)], "retry_count": 0}
    )
    assert s["review_status"] == "reject_to_planner"
    assert s["retry_count"] == 1

    # 툴 에러 → executor 라우팅 (UL 위반보다 우선)
    s = await specialized_review_node({
        "execution_results": [
            {"task_name": "search_products", "tool_name": "search_products",
             "status": "error", "step": 2, "error_message": "timeout"},
            _ul(False),
        ],
        "retry_count": 0,
    })
    assert s["review_status"] == "reject_to_executor", s

    # 3회 소진 → 부분 실패 확정 + pass (무한루프 방지)
    s = await specialized_review_node(
        {"execution_results": [_ul(False)], "retry_count": MAX_RETRIES}
    )
    assert s["review_status"] == "pass", s
    assert len(s["failed_items"]) == 1
    assert s["failed_items"][0]["status"] == "failed"
    print("  reviewer OK")


async def test_executor():
    plan = _deterministic_plan(
        {"age": 30, "gender": "female", "weight_kg": 60}, ["vitamin_d"]
    )
    # 배치: step1 단독, step2+3 그룹, step4 단독 → 3배치
    batches = _batches(plan)
    assert [len(b) for b in batches] == [1, 2, 1], batches

    # MCP 미구동 → fallback으로 전부 success
    s = await executor_node({"execution_plan": plan})
    results = s["execution_results"]
    assert len(results) == 4
    assert all(r["status"] == "success" for r in results), results
    ri = next(r for r in results if r["task_name"] == "calculate_dynamic_ri")
    # DB 연동 시 실제 RI, DB 불가 시 stub. 어느 경로든 vitamin_d는 양수.
    assert ri["result"]["custom_ri"]["vitamin_d"]["value"] > 0
    print("  executor OK")


async def test_compliance():
    assert _mask_name("홍길동") == "홍*동"
    assert _mask_name("이수") == "이*"
    assert _mask_birth("1990-01-01") == "19**-**-**"
    s = await legal_compliance_node({
        "aggregated_report": {
            "title": "t",
            "user_profile": {
                "name": "홍길동", "birth_date": "1990-01-01",
                "age": 30, "gender": "female", "weight_kg": 60,
                "is_pii": {"name": True, "birth_date": True},
            },
            "calculated_target": {}, "timing_guidance": {},
            "products": [], "guidelines": [], "failed_items": [],
        }
    })
    fr = s["final_report"]
    assert fr["user_profile"]["name"] == "홍*동"
    assert "홍길동" not in fr["html"]  # 원본 이름 미노출
    assert "의료법상" in fr["html"]    # disclaimer 포함
    print("  compliance OK")


async def main():
    await test_reviewer()
    await test_executor()
    await test_compliance()
    print("ALL PASS")


if __name__ == "__main__":
    asyncio.run(main())
