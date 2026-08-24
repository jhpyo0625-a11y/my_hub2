import re

import config
from schemas.state import State
from schemas.models import FinalReport
from prompts.report_template import render_report

DISCLAIMER = (
    "본 추천 리포트는 AI 분석에 기반한 참고용 영양 정보이며, "
    "의료법상 의사의 진단이나 처방을 대신할 수 없습니다."
)

_GENDER_KO = {"male": "남성", "female": "여성"}
_COVERAGE_KO = {  # compute_intake_coverage status -> (라벨, tone)
    "deficient": ("부족", "blue"),
    "adequate": ("적정", "green"),
    "excess": ("과잉", "orange"),
}
_LABFLAG_KO = {  # LabResult flag -> (라벨, tone)
    "low": ("낮음", "blue"),
    "normal": ("정상", "green"),
    "high": ("높음", "orange"),
}

# 숫자 토큰: 정수/소수(1000, 1.2 등). 산문 숫자 안전 검증에 사용.
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def _numbers_in(text: str) -> set[str]:
    """텍스트의 숫자 토큰 집합. LLM 산문의 숫자가 엔진 유래 숫자의 부분집합인지
    확인하는 데 쓴다(주입된 가짜 숫자 탐지)."""
    return set(_NUM_RE.findall(text or ""))


def _mask_name(name: str) -> str:
    if not name:
        return name
    if len(name) <= 1:
        return "*"
    if len(name) == 2:
        return name[0] + "*"
    return name[0] + "*" * (len(name) - 2) + name[-1]


def _mask_birth(birth: str) -> str:
    # "1990-01-01" -> "19**-**-**": 앞 2자리(세기)만 노출.
    if not birth or len(birth) < 2:
        return "****"
    return birth[:2] + "**-**-**"


def _mask_profile(profile: dict) -> dict:
    """is_pii로 태깅된 필드만 마스킹. DB 원본은 건드리지 않음(여기서만 복사본 가공)."""
    masked = dict(profile)
    is_pii = profile.get("is_pii", {})
    if is_pii.get("name"):
        masked["name"] = _mask_name(profile.get("name", ""))
    if is_pii.get("birth_date") and profile.get("birth_date"):
        masked["birth_date"] = _mask_birth(profile["birth_date"])
    return masked


def _build_context(report: dict, profile: dict, failed: list) -> dict:
    """현 aggregated_report 필드를 리포트 템플릿(case*.json 계열) 섹션으로 매핑.

    데이터 간극(중요): case*.json 의 exam.groups/badges/summary.chips/nutrients.bar·
    gauge 는 현 파이프라인이 산출하지 않는다 → 조작하지 않고 생략한다. 여기서는
    엔진이 실제로 내놓는 값만 채운다: 프로필, 권장(RI)+충족률, UL 검증, 복용시간,
    검사수치, 제품, 근거.
    """
    target = report.get("calculated_target", {}).get("custom_ri", {})
    coverage = report.get("coverage", {}).get("coverage", {})
    nutrients = []
    for code, info in target.items():
        cov = coverage.get(code, {}) or {}
        label, tone = _COVERAGE_KO.get(cov.get("status"), ("", ""))
        nutrients.append({
            "name": code,
            "value": info.get("value"),
            "unit": info.get("unit", ""),
            "pct": cov.get("pct"),
            "status_label": label,
            "status_tone": tone,
        })

    ul_violations = [
        {"nutrient": v.get("nutrient"), "total_intake": v.get("total_intake"),
         "ul_limit": v.get("ul_limit")}
        for v in report.get("ul_check", {}).get("ul_violations", [])
    ]

    schedule = report.get("timing_guidance", {}).get("time_separated_schedule", {})
    timing = {
        "am": ", ".join(schedule.get("morning_AM", [])),
        "pm": ", ".join(schedule.get("evening_PM", [])),
        "cautions": report.get("timing_guidance", {}).get("cautions", []),
    }

    lab_results = []
    for l in report.get("lab_results", {}).get("results", []):
        label, tone = _LABFLAG_KO.get(l.get("flag"), ("", "gray"))
        lab_results.append({
            "test_name": l.get("test_name"), "value": l.get("value"),
            "unit": l.get("unit", ""), "flag_label": label, "flag_tone": tone,
        })

    products = [
        {"name": p.get("product_name", ""), "brand": p.get("brand") or ""}
        for p in report.get("products", [])[:5]
    ]
    guidelines = [
        {"text": g.get("text", ""), "source": g.get("source", "")}
        for g in report.get("guidelines", []) if g
    ]

    return {
        "title": report.get("title", "영양 리포트"),
        "profile": {
            "name": profile.get("name"),
            "age": profile.get("age"),
            "gender": _GENDER_KO.get(profile.get("gender"), profile.get("gender")),
            "weight": profile.get("weight_kg"),
        },
        "failure_notice": bool(failed),
        "nutrients": nutrients,
        "ul_violations": ul_violations,
        "timing": timing,
        "lab_results": lab_results,
        "products": products,
        "guidelines": guidelines,
        "disclaimer": DISCLAIMER,
        "prose": None,
    }


def _llm_prose(context: dict) -> str | None:
    """엔진 숫자를 읽기전용 컨텍스트로 주입해 한국어 설명 산문만 생성. 실패 시 None.

    호출 자체는 COMPLIANCE_LLM_PROSE=1 이고 키가 있을 때만 도달한다.
    """
    from langchain_openai import ChatOpenAI
    from prompts.report_prompt import REPORT_PROSE_PROMPT

    p = context["profile"]
    profile_txt = (f"나이 {p['age']} · 성별 {p['gender']}"
                   + (f" · 체중 {p['weight']}kg" if p.get("weight") else ""))
    lines = [f"- {n['name']}: 맞춤 권장 {n['value']}{n['unit']}"
             + (f", 충족률 {n['pct']}%" if n["pct"] is not None else "")
             for n in context["nutrients"]]
    for u in context["ul_violations"]:
        lines.append(f"- 상한초과 {u['nutrient']}: 총섭취 {u['total_intake']} / 상한 {u['ul_limit']}")
    numbers_txt = "\n".join(lines) or "(수치 없음)"

    llm = ChatOpenAI(
        model=config.OPENAI_MODEL,
        api_key=config.OPENAI_API_KEY,
        base_url=config.OPENAI_BASE_URL,
        temperature=0,
    )
    msg = REPORT_PROSE_PROMPT.format(profile=profile_txt, numbers=numbers_txt)
    resp = llm.invoke(msg)
    text = getattr(resp, "content", "") or ""
    return text.strip() or None


def _maybe_prose(context: dict, deterministic_html: str) -> str | None:
    """게이트 OFF/키없음/LLM실패/숫자위반이면 None(→결정적 렌더). 안전할 때만 산문 반환.

    숫자 안전: 산문의 숫자 토큰이 결정적 렌더(엔진 유래)의 숫자 집합의 부분집합이어야
    한다. 새 숫자가 하나라도 있으면 폐기(파이프라인 하드블록 아님, 안전 강등).
    """
    if config.COMPLIANCE_LLM_PROSE != "1" or not config.OPENAI_API_KEY:
        return None
    try:
        prose = _llm_prose(context)
    except Exception as e:  # noqa: BLE001
        print(f"  [Compliance] LLM 산문 실패, 결정적 렌더로 폴백: {e}")
        return None
    if not prose:
        return None
    allowed = _numbers_in(deterministic_html)
    injected = _numbers_in(prose) - allowed
    if injected:
        print(f"  [Compliance] 산문 숫자 위반(엔진 미유래 {sorted(injected)}) → 폐기")
        return None
    return prose


def _render_html(report: dict, profile: dict, failed: list) -> str:
    """결정적 Jinja 렌더 + (선택) LLM 설명 산문. 숫자/표는 항상 결정적."""
    context = _build_context(report, profile, failed)
    deterministic_html = render_report(context)
    prose = _maybe_prose(context, deterministic_html)
    if prose is None:
        return deterministic_html
    context["prose"] = prose
    return render_report(context)


async def legal_compliance_node(state: State) -> State:
    print(
        "\n[Node 6] Compliance Agent: "
        "PII 마스킹 및 HTML 렌더링 중..."
    )

    report = state.get("aggregated_report", {})
    profile = report.get("user_profile", {})
    failed = report.get("failed_items", [])

    # 사용자 노출 시점에만 마스킹. DB 원본은 그대로 유지.
    masked_profile = _mask_profile(profile)
    html = _render_html(report, masked_profile, failed)

    state["final_report"] = {
        "html": html,
        "user_profile": masked_profile,
        "disclaimer": DISCLAIMER,
        "partial_failure": bool(failed),
        "compliance_checked": True,
    }
    state["final_report"] = FinalReport.model_validate(
        state["final_report"]).model_dump()
    return state
