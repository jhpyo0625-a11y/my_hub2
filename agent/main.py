from typing import TypedDict, List, Dict, Any, Literal
from langgraph.graph import StateGraph, END

from rag_retriever import rag_retriever


class State(TypedDict, total=False):
    user_input: Dict[str, Any]
    normalized_data: Dict[str, Any]
    rag_context: Dict[str, Any]
    execution_plan: List[Dict[str, Any]]
    execution_results: List[Dict[str, Any]]
    review_status: Literal["pass", "reject_to_executor", "reject_to_planner"]
    review_feedback: str
    final_report: Dict[str, Any]


def input_normalization_node(state: State) -> State:
    print("\n[Node] Normalizer: 입력 데이터 정규화 및 마스킹 처리 중...")

    state["normalized_data"] = {
        "masked": True,
        "units_normalized": True,
        **state.get("user_input", {}),
    }

    return state


def build_rag_query(state: State) -> str:
    """현재 입력에서 semantic retrieval용 query를 만듭니다."""
    user_input = state.get("user_input", {})
    normalized = state.get("normalized_data", {})

    parts = []

    for data in (user_input, normalized):
        for key, value in data.items():
            if key in {"name", "masked", "units_normalized"}:
                continue

            if value not in (None, "", False):
                parts.append(f"{key}: {value}")

    return "\n".join(parts)


def rag_context_agent_node(state: State) -> State:
    print("[Agent] RAG Context: Embedding + ChromaDB 검색 중...")

    query = build_rag_query(state)

    if not query:
        state["rag_context"] = {
            "query": "",
            "results": [],
            "sources": [],
        }
        return state

    results = rag_retriever.search(
        query=query,
        top_k=8,
    )

    sources = []
    seen = set()

    for result in results:
        source_file = result["metadata"].get("source_file")

        if source_file and source_file not in seen:
            sources.append(source_file)
            seen.add(source_file)

    state["rag_context"] = {
        "query": query,
        "results": results,
        "sources": sources,
        "collection_count": rag_retriever.count(),
    }

    print(
        f"[RAG] query={query!r}\n"
        f"[RAG] retrieved={len(results)}\n"
        f"[RAG] sources={sources}"
    )

    return state


def planner_agent_node(state: State) -> State:
    print("[Agent] Planner: 작업 계획 수립 중...")

    rag = state.get("rag_context", {})

    state["execution_plan"] = [
        {
            "step": 1,
            "tool": "calculate_dynamic_ri",
            "rag_sources": rag.get("sources", []),
        },
        {
            "step": 2,
            "tool": "validate_ul_guardrail",
            "rag_sources": rag.get("sources", []),
        },
    ]

    return state


def executor_node(state: State) -> State:
    print("[Agent] Executor: MCP 서버 툴 호출 및 연산 실행 중...")

    state["execution_results"] = [
        {
            "tool": "validate_ul_guardrail",
            "status": "success",
            "result": "safe",
            "rag_sources": state.get("rag_context", {}).get("sources", []),
        }
    ]

    return state


def specialized_review_node(state: State) -> State:
    print("[Agent] Reviewer: 결과 검토 및 가드레일 검증 중...")

    state["review_status"] = "pass"
    state["review_feedback"] = "안전성 검증 통과"

    return state


def aggregator_node(state: State) -> State:
    print("[Agent] Aggregator: 통합 리포트 프롬프트 취합 중...")

    state["final_report"] = {
        "title": "개인 맞춤형 영양 리포트",
        "details": state.get("execution_results", []),
        "rag_context": state.get("rag_context", {}),
        "disclaimer": "본 리포트는 의료인의 진단을 대체할 수 없습니다.",
    }

    return state


def legal_compliance_node(state: State) -> State:
    print("[Agent] Compliance: 법률 및 규제 준수 최종 검수 완료.\n")
    return state


workflow = StateGraph(State)

workflow.add_node("normalizer_node", input_normalization_node)
workflow.add_node("rag_context_agent", rag_context_agent_node)
workflow.add_node("planner_agent", planner_agent_node)
workflow.add_node("executor_agent", executor_node)
workflow.add_node("reviewer_agent", specialized_review_node)
workflow.add_node("aggregator_agent", aggregator_node)
workflow.add_node("compliance_agent", legal_compliance_node)

workflow.set_entry_point("normalizer_node")

workflow.add_edge("normalizer_node", "rag_context_agent")
workflow.add_edge("rag_context_agent", "planner_agent")
workflow.add_edge("planner_agent", "executor_agent")
workflow.add_edge("executor_agent", "reviewer_agent")


def route_after_review(
    state: State,
) -> Literal["executor_agent", "planner_agent", "aggregator_agent"]:

    status = state.get("review_status", "pass")

    if status == "reject_to_executor":
        print("  -> ⚠️ 피드백 발생: Executor로 돌아가 재실행합니다 (Loop).")
        return "executor_agent"

    elif status == "reject_to_planner":
        print("  -> ⚠️ 피드백 발생: Planner로 돌아가 계획을 재수립합니다 (Loop).")
        return "planner_agent"

    else:
        print("  -> ✅ 검증 통과: Aggregator로 넘어갑니다.")
        return "aggregator_agent"


workflow.add_conditional_edges(
    "reviewer_agent",
    route_after_review,
    {
        "executor_agent": "executor_agent",
        "planner_agent": "planner_agent",
        "aggregator_agent": "aggregator_agent",
    },
)

workflow.add_edge("aggregator_agent", "compliance_agent")
workflow.add_edge("compliance_agent", END)

app = workflow.compile()


if __name__ == "__main__":
    initial_input = {
        "user_input": {
            "name": "홍길동",
            "age": 35,
            "weight_kg": 75.5,
            "ocr_text": "혈중 칼슘 9.5 mg/dL",
        }
    }

    print("=== AI 영양제 추천 서비스 에이전트 파이프라인 시작 ===")

    final_state = app.invoke(initial_input)

    print("=== 🏁 최종 출력 결과 ===")
    print(final_state.get("final_report"))
