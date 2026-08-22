import html as html_lib

from schemas.state import State

DISCLAIMER = (
    "본 추천 리포트는 AI 분석에 기반한 참고용 영양 정보이며, "
    "의료법상 의사의 진단이나 처방을 대신할 수 없습니다."
)


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


def _render_html(report: dict, profile: dict, failed: list) -> str:
    esc = html_lib.escape
    target = report.get("calculated_target", {}).get("custom_ri", {})
    timing = report.get("timing_guidance", {})
    schedule = timing.get("time_separated_schedule", {})
    products = report.get("products", [])
    guidelines = [g for g in report.get("guidelines", []) if g]

    rows = "".join(
        f"<tr><td>{esc(code)}</td><td>{esc(str(info.get('value')))} "
        f"{esc(str(info.get('unit', '')))}</td></tr>"
        for code, info in target.items()
    ) or "<tr><td colspan='2'>산출된 목표치 없음</td></tr>"

    product_items = "".join(
        f"<li>{esc(str(p.get('product_name', '')))} "
        f"({esc(str(p.get('brand') or ''))})</li>"
        for p in products[:5]
    ) or "<li>추천 제품 없음</li>"

    guide_items = "".join(
        f"<li>{esc(str(g.get('text', '')))} "
        f"<span class=\"cite\">— {esc(str(g.get('source', '')))}</span></li>"
        for g in guidelines
    ) or "<li>참고 근거 없음</li>"

    failure_notice = ""
    if failed:
        failure_notice = (
            "<div class='notice'>일부 항목은 자동 검증을 완료하지 못해 "
            "이번 결과에서 제외되었습니다. 해당 항목은 전문가와 상담하시기를 "
            "권장드립니다.</div>"
        )

    am = ", ".join(esc(x) for x in schedule.get("morning_AM", [])) or "-"
    pm = ", ".join(esc(x) for x in schedule.get("evening_PM", [])) or "-"

    return f"""<section class="nutrition-report">
  <h1>{esc(report.get('title', '영양 리포트'))}</h1>
  <p class="profile">이름: {esc(str(profile.get('name')))} /
     나이: {esc(str(profile.get('age')))} /
     성별: {esc(str(profile.get('gender')))} /
     체중: {esc(str(profile.get('weight_kg')))}kg</p>
  {failure_notice}
  <h2>맞춤 권장 섭취량</h2>
  <table><thead><tr><th>영양소</th><th>목표</th></tr></thead>
    <tbody>{rows}</tbody></table>
  <h2>복용 시간</h2>
  <p>아침: {am} / 저녁: {pm}</p>
  <h2>추천 제품</h2>
  <ul>{product_items}</ul>
  <h2>참고 근거</h2>
  <ul>{guide_items}</ul>
  <footer class="disclaimer">{esc(DISCLAIMER)}</footer>
</section>"""


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
    return state
