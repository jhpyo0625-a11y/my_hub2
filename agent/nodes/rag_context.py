from schemas.state import State
from rag_retriever import rag_retriever


def rag_context_agent_node(state: State) -> State:
    print(
        "\n[Node 2] RAG Context Agent: "
        "시맨틱 쿼리 재구조화 및 가이드라인 검색..."
    )

    normalized_data = state.get(
        "normalized_data",
        {}
    )

    ocr_data = state.get(
        "ocr_result",
        {}
    ).get(
        "extracted_indicators",
        {}
    )

    rag_queries = []

    # 이상 수치 검색
    for indicator, info in ocr_data.items():
        if info.get("status") in [
            "warning",
            "deficient",
        ]:
            rag_queries.append(
                f"{indicator} "
                f"{info.get('status')} "
                f"개선을 위한 영양소 섭취 가이드라인"
            )

    # 기본 프로필 검색
    rag_queries.append(
        f"{normalized_data.get('age')}세 "
        f"체중 {normalized_data.get('weight_kg')}kg "
        f"영양소 권장 기준"
    )

    search_results = []

    for query in rag_queries:
        docs = rag_retriever.search(
            query=query,
            top_k=2,
        )

        search_results.extend(docs)

    state["rag_context"] = search_results

    print(
        f"  -> RAG 검색 완료: "
        f"총 {len(search_results)}건"
    )

    return state
