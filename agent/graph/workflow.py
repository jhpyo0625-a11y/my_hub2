from typing import Literal

from langgraph.graph import StateGraph, END

from schemas.state import State

from nodes.normalizer import input_normalization_node
from nodes.planner import planner_agent_node
from nodes.executor import executor_node
from nodes.reviewer import specialized_review_node
from nodes.aggregator import aggregator_node
from nodes.compliance import legal_compliance_node


def route_after_review(
    state: State,
) -> Literal["executor_agent", "planner_agent", "aggregator_agent"]:
    status = state.get("review_status", "pass")

    if status == "reject_to_executor":
        print("  -> ⚠️ Executor로 루프하여 재연산 수행.")
        return "executor_agent"

    if status == "reject_to_planner":
        print("  -> ⚠️ Planner로 루프하여 작업 계획 재수립.")
        return "planner_agent"

    print("  -> ✅ 검수 통과: Aggregator로 이동.")
    return "aggregator_agent"


def build_workflow():
    workflow = StateGraph(State)

    workflow.add_node("normalizer_node", input_normalization_node)
    workflow.add_node("planner_agent", planner_agent_node)
    workflow.add_node("executor_agent", executor_node)
    workflow.add_node("reviewer_agent", specialized_review_node)
    workflow.add_node("aggregator_agent", aggregator_node)
    workflow.add_node("compliance_agent", legal_compliance_node)

    workflow.set_entry_point("normalizer_node")

    # RAG는 Aggregator 단계로 이동 (계획 전 검색 노드 제거).
    workflow.add_edge("normalizer_node", "planner_agent")
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

    return workflow.compile()


graph = build_workflow()
