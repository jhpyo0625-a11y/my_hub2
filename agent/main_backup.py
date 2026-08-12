from typing import TypedDict, List, Dict, Any, Literal
from langgraph.graph import StateGraph, END

# 1. 상태(State) 정의 (rag_context 추가)
class State(TypedDict):
    user_input: Dict[str, Any]
    normalized_data: Dict[str, Any]
    execution_plan: List[Dict[str, Any]]
    execution_results: List[Dict[str, Any]]
    review_status: Literal["pass", "reject_to_executor", "reject_to_planner"]
    review_feedback: str
    rag_context: str                 # 🆕 RAG 에이전트가 검색한 가이드라인 텍스트
    final_report: Dict[str, Any]

# 2. 메인 노드 및 에이전트 함수 정의
def input_normalization_node(state: State) -> State:
    print("\n[Node] Normalizer: 입력 데이터 정규화 및 마스킹 처리 중...")
    state["normalized_data"] = {"masked": True, **state.get("user_input", {})}
    return state

def planner_agent_node(state: State) -> State:
    print("[Agent] Planner: 작업 계획 수립 중...")
    state["execution_plan"] = [{"step": 1, "tool": "calculate_dynamic_ri"}]
    return state

def executor_node(state: State) -> State:
    print("[Agent] Executor: MCP 서버(NeonDB) 툴 호출 및 수치 연산 실행 중...")
    state["execution_results"] = [{"nutrient": "비타민 D", "recommended_dose": "1000 IU", "status": "safe"}]
    return state

def specialized_review_node(state: State) -> State:
    print("[Agent] Reviewer: 결과 검토 및 상한선(UL) 가드레일 검증 중...")
    state["review_status"] = "pass" 
    state["review_feedback"] = "수치적 안전성 검증 통과"
    return state

# RAG 에이전트 노드
def rag_context_agent_node(state: State) -> State:
    print("[Agent] RAG Retriever: 추천된 영양소에 대한 KDRI 원문 및 설명 검색 중...")
    # 예시 로직: execution_results를 바탕으로 Vector DB(Qdrant) 검색
    state["rag_context"] = (
        "KDRI 가이드라인에 따르면, 비타민 D는 칼슘 흡수를 돕고 뼈 건강에 필수적이며, "
        "한국인의 상당수가 실내 활동 증가로 인해 결핍 상태에 놓여 있습니다."
    )
    return state

def aggregator_node(state: State) -> State:
    print("[Agent] Aggregator: 수치 결과(Executor)와 문맥(RAG)을 통합 리포트로 취합 중...")
    state["final_report"] = {
        "title": "개인 맞춤형 영양 리포트",
        "prescription_data": state.get("execution_results", []),
        "expert_guideline": state.get("rag_context", ""), # 🆕 RAG 데이터 병합
        "disclaimer": "본 리포트는 의료인의 진단을 대체할 수 없습니다."
    }
    return state

def legal_compliance_node(state: State) -> State:
    print("[Agent] Compliance: 의료법 및 규제 준수 최종 검수 완료.\n")
    return state


# 3. 그래프 구성 및 라우팅 설정
workflow = StateGraph(State)

# 노드 등록
workflow.add_node("normalizer_node", input_normalization_node)
workflow.add_node("planner_agent", planner_agent_node)
workflow.add_node("executor_agent", executor_node)
workflow.add_node("reviewer_agent", specialized_review_node)
workflow.add_node("rag_agent", rag_context_agent_node) # 🆕 RAG 노드 등록
workflow.add_node("aggregator_agent", aggregator_node)
workflow.add_node("compliance_agent", legal_compliance_node)

# 선형 흐름 (전반부)
workflow.set_entry_point("normalizer_node")
workflow.add_edge("normalizer_node", "planner_agent")
workflow.add_edge("planner_agent", "executor_agent")
workflow.add_edge("executor_agent", "reviewer_agent")

# 조건부 흐름 (피드백 루프 및 RAG 연결)
def route_after_review(state: State) -> Literal["executor_agent", "planner_agent", "rag_agent"]:
    status = state.get("review_status", "pass")
    if status == "reject_to_executor":
        print("  -> ⚠️ 피드백 발생: Executor로 루프.")
        return "executor_agent"
    elif status == "reject_to_planner":
        print("  -> ⚠️ 피드백 발생: Planner로 루프.")
        return "planner_agent"
    else:
        # ✅ 통과 시 통합 에이전트가 아닌 'RAG 에이전트'로 이동하여 설명 문구를 생성
        print("  -> ✅ 수치 검증 통과: RAG 에이전트로 이동하여 가이드라인 검색.")
        return "rag_agent"

workflow.add_conditional_edges(
    "reviewer_agent",
    route_after_review,
    {
        "executor_agent": "executor_agent",
        "planner_agent": "planner_agent",
        "rag_agent": "rag_agent" # 🆕 통과 시 RAG로 연결
    }
)

# 후반부 흐름 (RAG -> 취합 -> 검수)
workflow.add_edge("rag_agent", "aggregator_agent")
workflow.add_edge("aggregator_agent", "compliance_agent")
workflow.add_edge("compliance_agent", END)

app = workflow.compile()

# --- 실행 테스트 ---
if __name__ == "__main__":
    initial_input = {"user_input": {"name": "홍길동"}}
    final_state = app.invoke(initial_input)
    
    print("=== 🏁 최종 출력 리포트 ===")
    print(final_state.get("final_report"))