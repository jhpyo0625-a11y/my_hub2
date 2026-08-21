import json

import config
from schemas.state import State
from schemas.planner import ExecutionPlan


def _contract_args(tool_name: str, normalized: dict, targets: list[str]) -> dict | None:
    """tool_name별 MCP 계약에 맞는 args를 (normalized, targets)에서 결정적으로 구성.

    args는 사용자 데이터로 완전히 결정되므로 LLM이 자유 생성할 필요가 없다.
    미지의 tool_name이면 None(수리 불가 → LLM args 유지).
    """
    age = normalized.get("age")
    gender = normalized.get("gender")
    weight = normalized.get("weight_kg")
    if tool_name == "calculate_dynamic_ri":
        return {"age": age, "gender": gender, "weight_kg": weight, "target_nutrients": targets}
    if tool_name == "search_products":
        return {"target_nutrients": targets}
    if tool_name == "check_nutrient_interactions":
        return {"nutrient_list": targets}
    if tool_name == "validate_ul_guardrail":
        # proposed_supps_intake는 Executor가 search_products 결과에서 주입.
        return {"current_supps_intake": {}, "diet_estimated_intake": {},
                "proposed_supps_intake": {}, "age": age, "gender": gender, "weight_kg": weight}
    return None


def _repair_args(plan: list[dict], normalized: dict, targets: list[str]) -> list[dict]:
    """LLM이 생성한 각 step의 args를 계약값으로 덮어쓴다(계약 위반 방지).

    LLM은 tool 선택/순서/parallel_group만 담당하고, args는 결정적 계약값을 쓴다.
    """
    for step in plan:
        fixed = _contract_args(step.get("tool_name"), normalized, targets)
        if fixed is not None:
            step["args"] = fixed
    return plan


def _deterministic_plan(normalized: dict, targets: list[str]) -> list[dict]:
    """LLM 없이도 항상 유효한 계획. MCP 계약(mcp_tool_specs.json) 준수.

    의존성: search_products 결과(proposed intake)가 validate_ul_guardrail의
    입력이므로 UL 검증은 마지막 순차 단계. RI 산출/제품검색/상호작용은 앞단.
    같은 parallel_group은 동시 실행.
    """
    age = normalized.get("age")
    gender = normalized.get("gender")
    weight = normalized.get("weight_kg")

    return [
        {
            "step": 1,
            "task_name": "calculate_dynamic_ri",
            "tool_name": "calculate_dynamic_ri",
            "args": {
                "age": age,
                "gender": gender,
                "weight_kg": weight,
                "target_nutrients": targets,
            },
            "description": "체중/연령/성별 반영 맞춤 권장섭취량(RI) 산출",
            "parallel_group": None,
        },
        {
            "step": 2,
            "task_name": "search_products",
            "tool_name": "search_products",
            "args": {"target_nutrients": targets},
            "description": "타깃 영양소를 공급하는 제품 검색",
            "parallel_group": 1,
        },
        {
            "step": 3,
            "task_name": "check_nutrient_interactions",
            "tool_name": "check_nutrient_interactions",
            "args": {"nutrient_list": targets},
            "description": "영양소 상호작용 검사 및 복용시간 분리",
            "parallel_group": 1,
        },
        {
            "step": 4,
            "task_name": "validate_ul_guardrail",
            "tool_name": "validate_ul_guardrail",
            "args": {
                "current_supps_intake": {},
                "diet_estimated_intake": {},
                # proposed_supps_intake는 step 2(search_products) 결과에서
                # Executor가 주입. 계획 시점엔 미확정이므로 빈 값.
                "proposed_supps_intake": {},
                "age": age,
                "gender": gender,
                "weight_kg": weight,
            },
            "description": "상한섭취량(UL) 초과 여부 검증",
            "parallel_group": None,
        },
    ]


def _llm_plan(normalized: dict, targets: list[str], feedback: str | None):
    """OpenAI structured output으로 ExecutionPlan 생성. 키/호출 실패 시 None."""
    if not config.OPENAI_API_KEY:
        return None
    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=config.OPENAI_MODEL,
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
            temperature=0,
        ).with_structured_output(ExecutionPlan, method="function_calling")
        # function_calling: strict json_schema는 args의 open dict(additionalProperties)
        # 를 거부하므로 완화된 tool-calling 모드 사용.

        sys = (
            "너는 영양제 추천 파이프라인의 오케스트레이터다. "
            "아래 사용자 데이터로 MCP 툴 실행계획(ExecutionPlan)을 세워라. "
            "가용 tool_name: calculate_dynamic_ri, validate_ul_guardrail, "
            "check_nutrient_interactions, search_products. "
            "calculate_dynamic_ri는 age/gender/weight_kg/target_nutrients, "
            "validate_ul_guardrail는 마지막에 수행(제품 검색 결과에 의존). "
            "동시 실행 가능한 step은 같은 parallel_group 정수로 묶어라."
        )
        usr = json.dumps(
            {"normalized": normalized, "target_nutrients": targets,
             "reviewer_feedback": feedback},
            ensure_ascii=False,
        )
        plan: ExecutionPlan = llm.invoke(
            [("system", sys), ("human", usr)]
        )
        return [s.model_dump() for s in plan.steps]
    except Exception as e:  # noqa: BLE001
        print(f"  [Planner Warning] LLM 계획 실패, fallback 사용: {e}")
        return None


async def planner_agent_node(state: State) -> State:
    print(
        "\n[Node 2] Planner Agent: "
        "오케스트레이터 LLM의 자율 작업 계획 수립..."
    )

    feedback = state.get("review_feedback")
    if feedback and state.get("retry_count", 0) > 0:
        print(f"  -> [재수립 모드] 이전 피드백 반영: {feedback}")

    normalized = state.get("normalized_data", {})
    targets = state.get("target_nutrients", [])

    llm_plan = _llm_plan(normalized, targets, feedback)
    # LLM args는 계약을 어길 수 있으므로 결정적 계약값으로 수리. deterministic은 이미 정확.
    plan = _repair_args(llm_plan, normalized, targets) if llm_plan \
        else _deterministic_plan(normalized, targets)

    state["execution_plan"] = plan
    return state
