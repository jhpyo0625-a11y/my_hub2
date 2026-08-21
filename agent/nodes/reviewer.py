from schemas.state import State

MAX_RETRIES = 3


async def specialized_review_node(state: State) -> State:
    print(
        "\n[Node 4] Reviewer Agent: "
        "계산 수치 정밀도 및 Safety Guardrail 검수 중..."
    )

    results = state.get("execution_results", [])
    retry = state.get("retry_count", 0)

    # 1) 툴 호출 자체 실패 → 실행(Executor) 문제
    tool_errors = [r for r in results if r.get("status") == "error"]

    # 2) 툴은 정상이나 UL 상한 초과 → 계획(Planner) 문제
    ul = next(
        (r for r in results if r.get("task_name") == "validate_ul_guardrail"),
        None,
    )
    ul_result = (ul or {}).get("result", {}) or {}
    ul_violation = bool(
        ul is not None
        and (not ul_result.get("is_safe", True) or ul_result.get("ul_violations"))
    )

    if tool_errors:
        problem = "executor"
    elif ul_violation:
        problem = "planner"
    else:
        problem = None

    if problem is None:
        state["review_status"] = "pass"
        state["review_feedback"] = "모든 연산 및 가드레일 검수 통과."
        return state

    # 3회 소진 후에도 실패 → 부분 실패로 확정하고 파이프라인은 계속.
    if retry >= MAX_RETRIES:
        failed = list(state.get("failed_items", []))
        if problem == "executor":
            for r in tool_errors:
                failed.append({
                    "step": r.get("step"),
                    "tool_name": r.get("tool_name"),
                    "status": "failed",
                    "reason": r.get("error_message", "툴 실행 오류"),
                })
        else:
            failed.append({
                "step": (ul or {}).get("step"),
                "tool_name": "validate_ul_guardrail",
                "status": "failed",
                "reason": "상한 섭취량(UL) 검증 반복 실패",
            })
        state["failed_items"] = failed
        state["review_status"] = "pass"
        state["review_feedback"] = (
            f"{MAX_RETRIES}회 재시도 소진, 일부 항목을 부분 실패로 확정."
        )
        print(f"  -> ⛔ 재시도 {MAX_RETRIES}회 초과: 부분 실패 확정, 계속 진행.")
        return state

    # 재시도 여유 있음 → 원인별 라우팅 + 카운트 증가
    state["retry_count"] = retry + 1
    if problem == "executor":
        state["review_status"] = "reject_to_executor"
        state["review_feedback"] = (
            "MCP 툴 호출 오류/타임아웃 감지. 재실행 필요."
        )
    else:
        state["review_status"] = "reject_to_planner"
        state["review_feedback"] = (
            "상한 섭취량(UL) 초과 항목 감지. 계획 재수립 및 추천 수치 하향 요망."
        )
    return state
