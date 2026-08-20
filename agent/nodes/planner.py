from schemas.state import State


def planner_agent_node(state: State) -> State:
    print(
        "\n[Node 3] Planner Agent: "
        "오케스트레이터 LLM의 자율 작업 계획 수립..."
    )

    feedback = state.get("review_feedback")

    if feedback:
        print(
            f"  -> [재수립 모드] "
            f"이전 피드백 반영: {feedback}"
        )

    normalized_data = state.get(
        "normalized_data",
        {}
    )

    dynamic_plan = [
        {
            "step": 1,
            "task_name": "calculate_dynamic_ri",
            "tool_name": "calculate_dynamic_ri_tool",
            "args": {
                "age": normalized_data.get("age"),
                "weight_kg": normalized_data.get("weight_kg"),
            },
            "description": (
                "체중 변수를 대입한 "
                "맞춤 권장 섭취량 산출"
            ),
        },
        {
            "step": 2,
            "task_name": "validate_ul_guardrail",
            "tool_name": "validate_ul_guardrail_tool",
            "args": {
                "weight_kg": normalized_data.get(
                    "weight_kg"
                ),
            },
            "description": (
                "상한 섭취량(UL) 초과 여부 검증"
            ),
        },
        {
            "step": 3,
            "task_name": "check_interactions",
            "tool_name": "check_interaction_tool",
            "args": {},
            "description": (
                "영양소 간 흡수 저해 및 충돌 검사"
            ),
        },
    ]

    state["execution_plan"] = dynamic_plan

    return state
