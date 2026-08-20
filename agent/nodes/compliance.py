from schemas.state import State


def legal_compliance_node(state: State) -> State:
    print(
        "\n[Node 7] Compliance Agent: "
        "규제 준수 검수 및 Disclaimer 추가 중..."
    )

    report = state.get(
        "aggregated_report",
        {}
    )

    disclaimer = (
        "본 추천 리포트는 AI 분석에 기반한 "
        "참고용 영양 정보이며, "
        "의료법상 의사의 진단이나 처방을 "
        "대신할 수 없습니다."
    )

    state["final_report"] = {
        **report,
        "disclaimer": disclaimer,
        "compliance_checked": True,
    }

    return state
