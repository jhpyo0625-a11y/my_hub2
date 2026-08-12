from typing import TypedDict, List, Dict, Any, Literal
from langgraph.graph import StateGraph, END

# 1. 상태(State) 정의
class State(TypedDict):
    user_input: Dict[str, Any]
    normalized_data: Dict[str, Any]
    execution_plan: List[Dict[str, Any]]
    execution_results: List[Dict[str, Any]]
    review_status: Literal["pass", "reject_to_executor", "reject_to_planner"]
    review_feedback: str
    final_report: Dict[str, Any]

# 2. 메인 노드 및 에이전트 함수 정의
def input_normalization_node(state: State) -> State:
    print("\n[Node] Normalizer: 입력 데이터 정규화 및 마스킹 처리 중...")
    state["normalized_data"] = {"masked": True, "units_normalized": True, **state["user_input"]}
    return state

def planner_agent_node(state: State) -> State:
    print("[Agent] Planner: 작업 계획 수립 중...")
    state["execution_plan"] = [{"step": 1, "tool": "calculate_dynamic_ri"}, {"step": 2, "tool": "validate_ul_guardrail"}]
    return state

def executor_node(state: State) -> State:
    print("[Agent] Executor: MCP 서버 툴 호출 및 연산 실행 중...")
    state["execution_results"] = [{"tool": "validate_ul_guardrail", "status": "success", "result": "safe"}]
    return state

def specialized_review_node(state: State) -> State:
    print("[Agent] Reviewer: 결과 검토 및 가드레일 검증 중...")
    # 예시: 여기를 "reject_to_executor"로 바꾸면 루프(Self-Correction)를 테스트할 수 있습니다.
    state["review_status"] = "pass" 
    state["review_feedback"] = "안전성 검증 통과"
    return state

def aggregator_node(state: State) -> State:
    print("[Agent] Aggregator: 통합 리포트 프롬프트 취합 중...")
    state["final_report"] = {
        "title": "개인 맞춤형 영양 리포트",
        "details": state.get("execution_results", []),
        "disclaimer": "본 리포트는 의료인의 진단을 대체할 수 없습니다."
    }
    return state

def legal_compliance_node(state: State) -> State:
    print("[Agent] Compliance: 법률 및 규제 준수 최종 검수 완료.\n")
    return state

# 3. 그래프 구성
workflow = StateGraph(State)

workflow.add_node("normalizer_node", input_normalization_node)
workflow.add_node("planner_agent", planner_agent_node)
workflow.add_node("executor_agent", executor_node)
workflow.add_node("reviewer_agent", specialized_review_node)
workflow.add_node("aggregator_agent", aggregator_node)
workflow.add_node("compliance_agent", legal_compliance_node)

workflow.set_entry_point("normalizer_node")
workflow.add_edge("normalizer_node", "planner_agent")
workflow.add_edge("planner_agent", "executor_agent")
workflow.add_edge("executor_agent", "reviewer_agent")

def route_after_review(state: State) -> Literal["executor_agent", "planner_agent", "aggregator_agent"]:
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
        "aggregator_agent": "aggregator_agent"
    }
)

workflow.add_edge("aggregator_agent", "compliance_agent")
workflow.add_edge("compliance_agent", END)

app = workflow.compile()

# --- 실행 테스트 로직 ---
if __name__ == "__main__":
    # 초기 테스트 입력 데이터
    initial_input = {
        "user_input": {
            "name": "홍길동",
            "age": 35,
            "weight_kg": 75.5,
            "ocr_text": "혈중 칼슘 9.5 mg/dL"
        }
    }
    
    print("=== AI 영양제 추천 서비스 에이전트 파이프라인 시작 ===")
    # app.invoke를 통해 초기 상태를 주입하고 파이프라인 실행
    final_state = app.invoke(initial_input)
    
    print("=== 🏁 최종 출력 결과 ===")
    print(final_state.get("final_report"))