from typing import Any, Literal

from pydantic import BaseModel, Field


# MCP 툴 이름과 1:1로 고정 (mcp/mcp_tool_specs.json 기준).
# Literal로 제한해 LLM structured output이 없는 툴을 계획에 넣는 것을 스키마에서 차단.
ToolName = Literal[
    "resolve_nutrient_codes",
    "normalize_medical_data",
    "fill_missing_profile",
    "calculate_dynamic_ri",
    "search_products",
    "check_nutrient_interactions",
    "validate_ul_guardrail",
    "compute_intake_coverage",
    "search_evidence",
]


class PlanStep(BaseModel):
    step: int
    task_name: str
    tool_name: ToolName
    args: dict[str, Any] = Field(default_factory=dict)
    description: str
    parallel_group: int | None = None
    # 같은 parallel_group 값을 가진 step들은 asyncio.gather로 동시 실행.
    # None인 step은 step 오름차순으로 단독 순차 실행.


class ExecutionPlan(BaseModel):
    steps: list[PlanStep]


class StepResult(BaseModel):
    """executor_node가 방출하는 결과 dict의 공용 스키마 (성공/에러 공통)."""
    step: int | None = None
    task_name: str
    tool_name: str
    status: str
    result: dict | None = None
    error_message: str | None = None
