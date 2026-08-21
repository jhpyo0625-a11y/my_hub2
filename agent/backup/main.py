import json
from typing import TypedDict, List, Dict, Any, Literal, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from langgraph.graph import StateGraph, END
from rag_retriever import rag_retriever


# ==========================================
# 1. LangGraph State Definition
# ==========================================
class State(TypedDict, total=False):

    user_input: Dict[str, Any]

    ocr_text: str  
    ocr_result: Dict[str, Any]       # OCR을 통해 추출된 구조화된 검진 데이터

    normalized_data: Dict[str, Any]

    rag_context: List[Dict[str, Any]] # RAG 검색 결과를 담는 리스트로 변경

    execution_plan: List[Dict[str, Any]]

    execution_results: List[Dict[str, Any]]

    review_status: Literal["pass", "reject_to_executor", "reject_to_planner", "fail"]

    review_feedback: str

    aggregated_report: Dict[str, Any]

    final_report: Dict[str, Any]
    
    retry_count: int                 # 무한 루프 방지를 위한 재시도 횟수


# ==========================================
# 2. OCR & Normalizer Nodes 
# ==========================================
def run_ocr_pipeline(image_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    OCR 처리 및 PII 비식별화 파이프라인 작동
    - 성명, 주민번호 등 민감정보 마스킹 처리 
    - 검진 수치 정규화 파싱
    """
    print(f"[OCR Node] 파일({filename}, {len(image_bytes)} bytes) 파싱 및 PII 비식별화 진행 중...")
    
    # TODO : Upstage Document AI 등을 거쳐 추출 및 정규화된 의료 데이터가 와야 함.
    parsed_medical_data = {
        "pii_masked": True,
        "raw_text": "혈중 비타민 D: 12.3 ng/mL, 혈중 칼슘: 9.5 mg/dL, 중성지방: 180 mg/dL",
        "extracted_indicators": {
            "Vitamin_D": {"value": 12.3, "unit": "ng/mL", "status": "deficient"},
            "Calcium": {"value": 9.5, "unit": "mg/dL", "status": "normal"},
            "Triglyceride": {"value": 180, "unit": "mg/dL", "status": "warning"},
        }
    }
    return parsed_medical_data


def input_normalization_node(state: State) -> State:
    print("\n[Node 1] Normalizer: 이미지 OCR 및 입력 데이터 정규화 처리 중...")
    
    user_input = state.get("user_input", {})
    image_bytes = user_input.get("image_bytes")
    filename = user_input.get("filename")

    if image_bytes:
        ocr_res = run_ocr_pipeline(image_bytes, filename)
        state["ocr_result"] = ocr_res
        state["ocr_text"] = ocr_res.get("raw_text", "")
    else:
        state["ocr_result"] = {"extracted_indicators": {}}
        state["ocr_text"] = ""

    state["normalized_data"] = {
        "masked": True,
        "units_normalized": True,
        "name": user_input.get("name", "익명"),
        "age": user_input.get("age", 30),
        "weight_kg": user_input.get("weight_kg", 60.0),
        "current_supplements": user_input.get("current_supplements", []),
    }
    return state


# ==========================================
# 3. RAG Context Agent 
# ==========================================
def rag_context_agent_node(state: State) -> State:
    """
    RAG 타겟 선정 및 Query Reformulation
    - 단순 raw-data가 아닌, 이상 수치 및 상호작용 관련 시맨틱 쿼리 생성
    """
    print("\n[Node 2] RAG Context Agent: 시맨틱 쿼리 재구조화 및 가이드라인 검색...")
    
    norm_data = state.get("normalized_data", {})
    ocr_data = state.get("ocr_result", {}).get("extracted_indicators", {})
    
    rag_queries = []
    
    # Target 1: 비정상 검진 수치 관련 영양 가이드라인 검색
    for indicator, info in ocr_data.items():
        if info.get("status") in ["warning", "deficient"]:
            rag_queries.append(f"{indicator} {info.get('status')} 개선을 위한 영양소 섭취 가이드라인")

    # Target 2: 기본 프로필 기반 KDRI 검색
    rag_queries.append(f"{norm_data.get('age')}세 체중 {norm_data.get('weight_kg')}kg 영양소 권장 기준")

    search_results = []
    for q in rag_queries:
        docs = rag_retriever.search(query=q, top_k=2)
        search_results.extend(docs)

    state["rag_context"] = search_results
    print(f"  -> RAG 검색 완료: 총 {len(search_results)}건의 참조 지식 수집")
    
    return state


# ==========================================
# 4. Planner Agent
# ==========================================
def planner_agent_node(state: State) -> State:
    """
    LLM 기반 오케스트레이션 및 동적 작업 계획 수립
    - 하드코딩 제거: 상태에 따라 필요한 MCP 툴 호출 DAG 구성
    """
    print("\n[Node 3] Planner Agent: 오케스트레이터 LLM의 자율 작업 계획 수립...")
    
    feedback = state.get("review_feedback")
    if feedback:
        print(f"  -> [재수립 모드] 이전 피드백 반영: {feedback}")

    # TODO : (시뮬레이션) LLM이 사용자 데이터를 바탕으로 JSON 형태의 실행 계획(Plan)을 생성해야 함
    dynamic_plan = [
        {
            "step": 1,
            "task_name": "calculate_dynamic_ri",
            "tool_name": "calculate_dynamic_ri_tool",
            "args": {
                "age": state["normalized_data"]["age"],
                "weight_kg": state["normalized_data"]["weight_kg"],
            },
            "description": "체중 변수를 대입한 맞춤 권장 섭취량 산출 [cite: 345]"
        },
        {
            "step": 2,
            "task_name": "validate_ul_guardrail",
            "tool_name": "validate_ul_guardrail_tool",
            "args": {
                "weight_kg": state["normalized_data"]["weight_kg"],
            },
            "description": "상한 섭취량(UL) 초과 여부 검증 [cite: 347]"
        },
        {
            "step": 3,
            "task_name": "check_interactions",
            "tool_name": "check_interaction_tool",
            "args": {},
            "description": "영양소 간 흡수 저해 및 충돌 검사 [cite: 349]"
        }
    ]
    
    state["execution_plan"] = dynamic_plan
    return state


# ==========================================
# 5. Executor Agent
# ==========================================
def executor_node(state: State) -> State:
    """
    플래너의 계획에 따라 실제 MCP 서버 툴 호출 및 연산 실행
    """
    print("\n[Node 4] Executor Agent: MCP 서버 툴 호출 및 연산 실행 중...")
    
    plan = state.get("execution_plan", [])
    results = []
    
    for task in plan:
        tool_name = task.get("tool_name")
        args = task.get("args", {})
        print(f"  [MCP Tool Call] {tool_name} 실행 중...")
        
        # TODO : 실제 환경에서는 JSON-RPC를 통해 독립된 Horizon MCP 서버 호출
        if tool_name == "calculate_dynamic_ri_tool":
            weight = float(args.get("weight_kg", 60))
            # 동적 RI 산출 공식 시뮬레이션
            res = {"vitamin_d_iu": round(1000 * (weight / 60) ** 0.75)}
        elif tool_name == "validate_ul_guardrail_tool":
            res = {"ul_exceeded": False, "exceeded_nutrients": []}
        elif tool_name == "check_interaction_tool":
            res = {"conflict_found": False, "timing_recommendation": "칼슘과 철분은 2시간 시차 복용 권장 [cite: 355]"}
        else:
            res = {"status": "success"}
            
        results.append({"task_name": task.get("task_name"), "output": res})
        
    state["execution_results"] = results
    return state


# ==========================================
# 6. Specialized Reviewer
# ==========================================
def specialized_review_node(state: State) -> State:
    """
    가드레일 안전성 검토 및 상태 반환
    """
    print("\n[Node 5] Reviewer Agent: 계산 수치 정밀도 및 Safety Guardrail 검수 중...")
    
    results = state.get("execution_results", [])
    retry_cnt = state.get("retry_count", 0)
    
    ul_pass = True
    for r in results:
        if r.get("task_name") == "validate_ul_guardrail":
            if r.get("output", {}).get("ul_exceeded"):
                ul_pass = False
                break

    if not ul_pass and retry_cnt < 2:
        state["review_status"] = "reject_to_planner"
        state["review_feedback"] = "상한 섭취량(UL) 초과 항목 감지. 추천 수치 하향 조정 요망. [cite: 354]"
        state["retry_count"] = retry_cnt + 1
    elif not ul_pass and retry_cnt < 2:
                state["review_status"] = "reject_to_planner"
                state["review_feedback"] = "상한 섭취량(UL) 초과 항목 감지. 추천 수치 하향 조정 요망. [cite: 354]"
                state["retry_count"] = retry_cnt + 1
    else:
        state["review_status"] = "pass"
        state["review_feedback"] = "모든 연산 및 가드레일 검수 통과."
        
    return state


# ==========================================
# 7. Aggregator Agent
# ==========================================
def aggregator_node(state: State) -> State:
    """
    수치 결과와 RAG 컨텍스트를 통합 리포트로 구조화
    """
    print("\n[Node 6] Aggregator Agent: 분석 결과 종합 및 리포트 취합 중...")
    
    exec_res = state.get("execution_results", [])
    rag_ctx = state.get("rag_context", [])
    # TODO : 추후 프롬프트 템플릿 구성 후 아래 내용을 해당 템플릿에 맞춰 아웃풋을 생성해줘야 함.
    state["aggregated_report"] = {
        "title": "개인 맞춤형 정밀 영양 리포트",
        "user_profile": state.get("normalized_data", {}),
        "health_indicators": state.get("ocr_result", {}).get("extracted_indicators", {}),
        "calculated_target": next((r["output"] for r in exec_res if r["task_name"] == "calculate_dynamic_ri"), {}),
        "timing_guidance": next((r["output"] for r in exec_res if r["task_name"] == "check_interactions"), {}),
        "guidelines": [doc.get("content") for doc in rag_ctx[:2]], # RAG에서 유효한 문서만 추출
    }
    return state


# ==========================================
# 8. Legal Compliance Agent
# ==========================================
def legal_compliance_node(state: State) -> State:
    """
    의료법 준수를 위한 검수 및 Disclaimer 추가 [cite: 76, 369]
    """
    print("\n[Node 7] Compliance Agent: 규제 준수 검수 및 Disclaimer 추가 중...\n")
    # TODO : 실제 환경에서는 의료법 준수 여부를 LLM 기반으로 검수 후, 필요 시 Disclaimer 문구를 동적으로 생성
    report = state.get("aggregated_report", {})
    disclaimer = (
        "본 추천 리포트는 AI 분석에 기반한 참고용 영양 정보이며, "
        "의료법상 의사의 진단이나 처방을 대신할 수 없습니다. [cite: 369]"
    )
    
    state["final_report"] = {
        **report,
        "disclaimer": disclaimer,
        "compliance_checked": True
    }
    return state


# ==========================================
# 9. Dynamic Edge Routing
# ==========================================
def route_after_review(
    state: State,
) -> Literal["executor_agent", "planner_agent", "aggregator_agent"]:
    """
    검증 상태(review_status)에 따른 분기 처리
    """
    # TODO : LLM 기반으로 reject_to_executor, reject_to_planner, pass를 동적으로 판단하도록 개선 가능
    status = state.get("review_status", "pass")

    if status == "reject_to_executor":
        print("  -> ⚠️ 피드백 발생: Executor로 루프하여 재연산 수행.")
        return "executor_agent"
    elif status == "reject_to_planner":
        print("  -> ⚠️ 피드백 발생: Planner로 루프하여 작업 계획 재수립.")
        return "planner_agent"
    else:
        print("  -> ✅ 수치 및 가드레일 통과: Aggregator로 이동.")
        return "aggregator_agent"


# ==========================================
# 10. LangGraph Workflow Building
# ==========================================
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

# LangGraph 컴파일
graph = workflow.compile()


# ==========================================
# 11. FastAPI Server & Endpoint Setup
# ==========================================
app = FastAPI(
    title="AI 영양제 추천 서비스 API",
    description="멀티 에이전트 오케스트레이션 및 MCP 툴 기반 정밀 영양 추천 API",
    version="1.2.0",
)


@app.post("/api/v1/recommend", summary="검진표 이미지 기반 개인 맞춤 영양 추천 생성")
async def recommend_nutrition(
    file: Optional[UploadFile] = File(None, description="검진표 이미지 또는 PDF 파일"),
    name: Optional[str] = Form(None, description="사용자 이름"),
    age: Optional[int] = Form(None, description="나이"),
    weight_kg: Optional[float] = Form(None, description="체중 (kg)"),
):
    try:
        image_bytes = None
        filename = None

        if file:
            image_bytes = await file.read()
            filename = file.filename

        user_input_dict = {
            "name": name,
            "age": age,
            "weight_kg": weight_kg,
            "image_bytes": image_bytes,
            "filename": filename,
            "current_supplements": [] # 폼에서 리스트를 받을 경우 확장 가능
        }

        # retry_count 초기화 추가
        initial_state: State = {
            "user_input": user_input_dict,
            "retry_count": 0 
        }

        # LangGraph 파이프라인 실행
        final_state = graph.invoke(initial_state)

        return {
            "status": "success",
            "data": final_state.get("final_report", {}),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"파이프라인 실행 중 오류 발생: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)