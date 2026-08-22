"""노드별 pre/post 체크. 각 함수는 이탈 문자열 list를 반환(빈 list = 통과)."""
import re
from nodes.reviewer import MAX_RETRIES

_TOOLS = {
    "calculate_dynamic_ri", "validate_ul_guardrail",
    "check_nutrient_interactions", "search_products",
}
_REQ_ARGS = {
    "calculate_dynamic_ri": {"age", "gender", "weight_kg", "target_nutrients"},
    "validate_ul_guardrail": {"current_supps_intake", "diet_estimated_intake",
                              "proposed_supps_intake", "age", "gender", "weight_kg"},
    "check_nutrient_interactions": {"nutrient_list"},
    "search_products": {"target_nutrients"},
}


def pre_normalizer(state) -> list[str]:
    return [] if "user_input" in state else ["user_input 없음"]


def post_normalizer(state) -> list[str]:
    nd = state.get("normalized_data") or {}
    p = []
    age = nd.get("age")
    if not isinstance(age, int) or age < 19:
        p.append(f"age 부적합(≥19 필요): {age}")
    if nd.get("gender") not in ("male", "female"):
        p.append(f"gender 부적합: {nd.get('gender')}")
    if nd.get("gender_defaulted"):
        p.append("sex 기본값 사용됨(성별 필수)")
    if nd.get("age_defaulted"):
        p.append("age 기본값 사용됨(누락, 스코프 불가)")
    if "is_pii" not in nd:
        p.append("is_pii 태그 없음")
    tn = state.get("target_nutrients")
    if not (isinstance(tn, list) and tn and all(isinstance(x, str) for x in tn)):
        p.append("target_nutrients 부적합")
    return p


def pre_planner(state) -> list[str]:
    p = []
    if "normalized_data" not in state:
        p.append("normalized_data 없음")
    if "target_nutrients" not in state:
        p.append("target_nutrients 없음")
    return p


def post_planner(state) -> list[str]:
    plan = state.get("execution_plan")
    if not isinstance(plan, list) or not plan:
        return ["execution_plan 없음/빈값"]
    p = []
    ul_step = sp_step = None
    for s in plan:
        tn = s.get("tool_name")
        if tn not in _TOOLS:
            p.append(f"미지 tool_name: {tn}")
            continue
        missing = _REQ_ARGS[tn] - set((s.get("args") or {}).keys())
        if missing:
            p.append(f"{tn} 필수 args 누락: {sorted(missing)}")
        if tn == "validate_ul_guardrail":
            ul_step = s.get("step")
        if tn == "search_products":
            sp_step = s.get("step")
    if ul_step is not None and sp_step is not None and not (ul_step > sp_step):
        p.append("validate_ul_guardrail가 search_products 뒤가 아님")
    return p


def pre_executor(state) -> list[str]:
    return [] if "execution_plan" in state else ["execution_plan 없음"]


def post_executor(state) -> list[str]:
    res = state.get("execution_results")
    if not isinstance(res, list) or not res:
        return ["execution_results 없음/빈값"]
    p = []
    for r in res:
        if r.get("status") not in ("success", "error"):
            p.append(f"status 부적합: {r.get('status')}")
    for r in res:
        if r.get("task_name") == "calculate_dynamic_ri" and r.get("status") == "success":
            cri = (r.get("result") or {}).get("custom_ri", {})
            for code, info in cri.items():
                v = (info or {}).get("value")
                if v is None or v == 0:
                    p.append(f"custom_ri 누출(0/None): {code}")
    return p


def pre_reviewer(state) -> list[str]:
    return [] if "execution_results" in state else ["execution_results 없음"]


def post_reviewer(state) -> list[str]:
    p = []
    if state.get("review_status") not in ("pass", "reject_to_executor", "reject_to_planner"):
        p.append(f"review_status 부적합: {state.get('review_status')}")
    if state.get("retry_count", 0) > MAX_RETRIES:
        p.append(f"retry_count 초과: {state.get('retry_count')}")
    for f in state.get("failed_items", []) or []:
        if f.get("status") != "failed" or "reason" not in f:
            p.append(f"failed_item 형식 오류: {f}")
    return p


def pre_aggregator(state) -> list[str]:
    return [] if "execution_results" in state else ["execution_results 없음"]


def post_aggregator(state) -> list[str]:
    rep = state.get("aggregated_report")
    if not isinstance(rep, dict):
        return ["aggregated_report 없음"]
    p = []
    for k in ("title", "user_profile", "calculated_target", "ul_check", "guidelines"):
        if k not in rep:
            p.append(f"필수키 없음: {k}")
    by_task = {
        r["task_name"]: r.get("result")
        for r in state.get("execution_results", [])
        if r.get("status") == "success"
    }
    if "calculated_target" in rep and rep["calculated_target"] != by_task.get("calculate_dynamic_ri", {}):
        p.append("calculated_target가 executor 결과와 불일치")
    if "ul_check" in rep and rep["ul_check"] != by_task.get("validate_ul_guardrail", {}):
        p.append("ul_check가 executor 결과와 불일치")
    g = rep.get("guidelines")
    if not isinstance(g, list) or not all(isinstance(x, str) for x in g):
        p.append("guidelines 형식 오류")
    return p


def pre_compliance(state) -> list[str]:
    return [] if "aggregated_report" in state else ["aggregated_report 없음"]


def post_compliance(state) -> list[str]:
    fr = state.get("final_report")
    if not isinstance(fr, dict):
        return ["final_report 없음"]
    p = []
    html = fr.get("html")
    if not isinstance(html, str) or not html.strip():
        p.append("html 비어있음")
        html = ""
    if "의료법상" not in (fr.get("disclaimer") or ""):
        p.append("disclaimer 정문구 없음")

    nd = state.get("normalized_data", {})
    raw_name = nd.get("name")
    raw_birth = nd.get("birth_date")
    if raw_name and raw_name != "익명" and raw_name in html:
        p.append("이름 평문 노출")
    if raw_name and raw_name != "익명" and fr.get("user_profile", {}).get("name") == raw_name:
        p.append("user_profile 이름 미마스킹")
    if raw_birth and raw_birth in html:
        p.append("생년월일 평문 노출")
    if re.search(r"\d{6}-\d{7}", html):
        p.append("주민등록번호 패턴 노출")
    if re.search(r"01\d-?\d{3,4}-?\d{4}", html):
        p.append("전화번호 패턴 노출")
    return p
