from schemas.state import State


def specialized_review_node(state: State) -> State:
    print(
        "\n[Node 5] Reviewer Agent: "
        "계산 수치 정밀도 및 Safety Guardrail 검수 중..."
    )

    results = state.get(
        "execution_results",
        []
    )

    retry_count = state.get(
        "retry_count",
        0
    )

    ul_pass = True

    for result in results:
        if result.get("task_name") == "validate_ul_guardrail":
            if result.get("output", {}).get(
                "ul_exceeded"
            ):
                ul_pass = False
                break

    if not ul_pass:
        if retry_count < 2:
            state["review_status"] = (
                "reject_to_planner"
            )

            state["review_feedback"] = (
                "상한 섭취량(UL) 초과 항목 감지. "
                "추천 수치 하향 조정 요망."
            )

            state["retry_count"] = (
                retry_count + 1
            )

        else:
            # retry를 모두 사용했는데도 안전성 검증 실패
            state["review_status"] = (
                "reject_to_executor"
            )

            state["review_feedback"] = (
                "UL 검증 실패가 반복되었습니다. "
                "추천 결과를 생성하지 않고 "
                "재검산이 필요합니다."
            )

    else:
        state["review_status"] = "pass"

        state["review_feedback"] = (
            "모든 연산 및 가드레일 검수 통과."
        )

    return state
