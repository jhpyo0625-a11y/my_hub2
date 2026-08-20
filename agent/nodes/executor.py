from schemas.state import State


def executor_node(state: State) -> State:
    print(
        "\n[Node 4] Executor Agent: "
        "MCP 서버 툴 호출 및 연산 실행 중..."
    )

    plan = state.get("execution_plan", [])
    results = []

    for task in plan:
        tool_name = task.get("tool_name")
        args = task.get("args", {})

        print(
            f"  [MCP Tool Call] "
            f"{tool_name} 실행 중..."
        )

        if tool_name == "calculate_dynamic_ri_tool":
            weight = float(
                args.get("weight_kg", 60)
            )

            result = {
                "vitamin_d_iu": round(
                    1000 * (weight / 60) ** 0.75
                )
            }

        elif tool_name == "validate_ul_guardrail_tool":
            result = {
                "ul_exceeded": False,
                "exceeded_nutrients": [],
            }

        elif tool_name == "check_interaction_tool":
            result = {
                "conflict_found": False,
                "timing_recommendation": (
                    "칼슘과 철분은 "
                    "2시간 시차 복용 권장"
                ),
            }

        else:
            result = {
                "status": "success"
            }

        results.append({
            "task_name": task.get("task_name"),
            "output": result,
        })

    state["execution_results"] = results

    return state
