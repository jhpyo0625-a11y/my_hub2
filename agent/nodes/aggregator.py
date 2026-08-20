from schemas.state import State


def aggregator_node(state: State) -> State:
    print(
        "\n[Node 6] Aggregator Agent: "
        "분석 결과 종합 및 리포트 취합 중..."
    )

    execution_results = state.get(
        "execution_results",
        []
    )

    rag_context = state.get(
        "rag_context",
        []
    )

    calculated_target = next(
        (
            result["output"]
            for result in execution_results
            if result["task_name"]
            == "calculate_dynamic_ri"
        ),
        {},
    )

    timing_guidance = next(
        (
            result["output"]
            for result in execution_results
            if result["task_name"]
            == "check_interactions"
        ),
        {},
    )

    state["aggregated_report"] = {
        "title": "개인 맞춤형 정밀 영양 리포트",

        "user_profile": state.get(
            "normalized_data",
            {}
        ),

        "health_indicators": (
            state.get(
                "ocr_result",
                {}
            ).get(
                "extracted_indicators",
                {}
            )
        ),

        "calculated_target": calculated_target,

        "timing_guidance": timing_guidance,

        "guidelines": [
            doc.get("content")
            for doc in rag_context[:2]
        ],
    }

    return state
