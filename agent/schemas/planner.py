
from typing import Any
from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    step: int
    task_name: str
    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    description: str


class ExecutionPlan(BaseModel):
    steps: list[PlanStep]