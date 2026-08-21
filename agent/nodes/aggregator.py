from schemas.state import State


def _rag_search(queries: list[str]) -> list[dict]:
    """확정된 결과 근거 보강용 RAG. 모델 로드/검색 실패 시 빈 리스트."""
    try:
        # lazy import: SentenceTransformer 로드는 무겁고 오프라인 실패 가능.
        from rag_retriever import rag_retriever

        docs: list[dict] = []
        for q in queries:
            docs.extend(rag_retriever.search(query=q, top_k=2))
        return docs
    except Exception as e:  # noqa: BLE001
        print(f"  [Aggregator] RAG 보강 생략 ({e})")
        return []


async def aggregator_node(state: State) -> State:
    print(
        "\n[Node 5] Aggregator Agent: "
        "결과 통합 및 RAG 지식 융합 중..."
    )

    results = state.get("execution_results", [])
    by_task = {
        r["task_name"]: r.get("result", {})
        for r in results
        if r.get("status") == "success"
    }

    indicators = state.get("ocr_result", {}).get("extracted_indicators", {})

    # 계획 시점이 아닌 결과 확정 후 RAG: "이 결과를 무엇으로 설명/보강할지"가 목적.
    queries = [
        f"{code} 영양소 권장 섭취 및 근거 가이드라인"
        for code in state.get("target_nutrients", [])
    ]
    for name, info in indicators.items():
        if info.get("status") in ("warning", "deficient"):
            queries.append(f"{name} {info.get('status')} 개선 영양 가이드라인")
    rag_context = _rag_search(queries)
    state["rag_context"] = rag_context

    state["aggregated_report"] = {
        "title": "개인 맞춤형 정밀 영양 리포트",
        "user_profile": state.get("normalized_data", {}),
        "health_indicators": indicators,
        "calculated_target": by_task.get("calculate_dynamic_ri", {}),
        "timing_guidance": by_task.get("check_nutrient_interactions", {}),
        "products": by_task.get("search_products", {}).get("products", []),
        "ul_check": by_task.get("validate_ul_guardrail", {}),
        "failed_items": state.get("failed_items", []),
        "guidelines": [d.get("content") for d in rag_context[:2]],
    }
    return state
