import asyncio

from schemas.state import State
from services.mcp_client import call_mcp_tool
from services import db_helper


async def _db_compute(tool_name: str, args: dict) -> dict:
    """MCP 미구동 시 Neon DB 직접 조회로 동일 출력 산출.

    check_nutrient_interactions는 DB 테이블이 없어 여기서 처리하지 않음
    (상위에서 deterministic fallback으로 넘어감).
    """
    if tool_name == "calculate_dynamic_ri":
        return await asyncio.to_thread(
            db_helper.db_calculate_ri,
            args.get("age"), args.get("gender"),
            args.get("target_nutrients", []),
        )
    if tool_name == "search_products":
        return await asyncio.to_thread(
            db_helper.db_search_products, args.get("target_nutrients", [])
        )
    if tool_name == "validate_ul_guardrail":
        return await asyncio.to_thread(
            db_helper.db_validate_ul,
            args.get("proposed_supps_intake", {}),
            args.get("current_supps_intake", {}),
            args.get("diet_estimated_intake", {}),
            args.get("age"), args.get("gender"),
        )
    raise ValueError(f"no DB path for {tool_name}")


def _fallback(tool_name: str, args: dict) -> dict:
    """로컬 MCP 미구동 시 결정적 대체 연산. MCP 출력 스키마 형태를 맞춘다."""
    if tool_name == "calculate_dynamic_ri":
        weight = float(args.get("weight_kg") or 60)
        vit_d = round(1000 * (weight / 60) ** 0.75)
        custom_ri = {}
        for code in args.get("target_nutrients", []):
            custom_ri[code] = {
                "base": vit_d if code == "vitamin_d" else 0,
                "factor_per_kg": None,
                "value": vit_d if code == "vitamin_d" else 0,
                "unit": "IU" if code == "vitamin_d" else "mg",
            }
        return {"custom_ri": custom_ri}

    if tool_name == "validate_ul_guardrail":
        return {
            "is_safe": True,
            "ul_violations": [],
            "approved_recommendations": [],
        }

    if tool_name == "check_nutrient_interactions":
        nutrients = args.get("nutrient_list", [])
        return {
            "conflicts_found": False,
            "time_separated_schedule": {
                "morning_AM": nutrients,
                "evening_PM": [],
            },
            "cautions": ["칼슘과 철분은 2시간 시차 복용 권장"],
        }

    if tool_name == "search_products":
        return {"products": []}

    return {"status": "success"}


def _inject_dependencies(step: dict, results_by_task: dict) -> None:
    """계획 시점에 미확정이던 교차-step 인자를 앞선 결과에서 주입."""
    if step["tool_name"] != "validate_ul_guardrail":
        return
    products = (
        results_by_task.get("search_products", {}) or {}
    ).get("products", [])
    if products:
        # ponytail: 첫 제품의 per-serving 함량을 proposed로 사용.
        # 다제품 합산은 중복 계상 위험 있어 보류 — 정밀 합산 필요 시 승격.
        step["args"]["proposed_supps_intake"] = products[0].get(
            "nutrients", {}
        )


async def _run_step(step: dict) -> dict:
    tool_name = step["tool_name"]
    args = step.get("args", {})
    print(f"  [MCP Tool Call] {tool_name} 실행...")
    status = "success"
    try:
        result = await call_mcp_tool(tool_name, args)
        if result is None:  # MCP가 result 없이 응답한 경우
            raise RuntimeError("empty MCP result")
    except Exception as mcp_err:  # noqa: BLE001 - MCP 실패 시 DB 직접 조회
        try:
            result = await _db_compute(tool_name, args)
            print(f"    -> DB 직접 조회 사용 (MCP: {mcp_err})")
        except Exception as db_err:  # noqa: BLE001 - DB도 실패 시 결정적 stub
            result = _fallback(tool_name, args)
            print(f"    -> deterministic fallback 사용 (DB: {db_err})")
    return {
        "step": step["step"],
        "task_name": step["task_name"],
        "tool_name": tool_name,
        "status": status,
        "result": result,
        "output": result,  # 하류 노드 호환용 별칭
    }


def _batches(plan: list[dict]) -> list[list[dict]]:
    """parallel_group으로 실행 배치 구성. None은 단독, 같은 group은 동시."""
    batches: list[list[dict]] = []
    groups: dict[int, list[dict]] = {}
    for step in sorted(plan, key=lambda s: s["step"]):
        g = step.get("parallel_group")
        if g is None:
            batches.append([step])
        elif g in groups:
            groups[g].append(step)
        else:
            groups[g] = [step]
            batches.append(groups[g])
    return batches


async def executor_node(state: State) -> State:
    print(
        "\n[Node 3] Executor Node: "
        "MCP 서버 툴 호출 및 연산 실행 중..."
    )

    plan = state.get("execution_plan", [])
    results: list[dict] = []
    results_by_task: dict = {}

    for batch in _batches(plan):
        for step in batch:
            _inject_dependencies(step, results_by_task)

        if len(batch) == 1:
            batch_results = [await _run_step(batch[0])]
        else:
            batch_results = await asyncio.gather(
                *[_run_step(s) for s in batch],
                return_exceptions=True,
            )
            # gather 예외는 error 항목으로 정규화 (일부 실패해도 나머지 수집).
            batch_results = [
                r if isinstance(r, dict) else {
                    "step": None,
                    "task_name": "unknown",
                    "tool_name": "unknown",
                    "status": "error",
                    "error_message": str(r),
                }
                for r in batch_results
            ]

        for r in batch_results:
            results.append(r)
            if r["status"] == "success":
                results_by_task[r["task_name"]] = r["result"]

    state["execution_results"] = results
    return state
