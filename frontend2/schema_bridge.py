# -*- coding: utf-8 -*-
"""화면 규격 ↔ 에이전트 규격 변환을 모아 둔 곳.

이 파일이 있는 이유 ---------------------------------------------------------
같은 값을 두 이름으로 부르고 있습니다.

    화면            에이전트/DB
    sex '여성'   ↔  gender 'female'
    email        ↔  id
    age '45'     ↔  age 45          (문자열 ↔ 정수)

변환이 server.py 여기저기 흩어져 있으면 한쪽만 고치는 일이 생기고, 실제로
그래서 어긋난 적이 있습니다. 경계를 넘는 변환은 **전부 여기서만** 합니다.

대응 관계의 근거는 schema/api_contract.md 이고, 필드 정의는
agent/schemas/models.py 와 같은 값을 씁니다.
"""
import json

# ---------------------------------------------------------------------------
# 성별 — 화면은 한글, 에이전트는 영문
# ---------------------------------------------------------------------------
SEX_TO_GENDER = {"남성": "male", "여성": "female"}
GENDER_TO_SEX = {v: k for k, v in SEX_TO_GENDER.items()}


def to_gender(sex):
    """'여성' → 'female'. 빈 값이나 모르는 값이면 None (보내지 않습니다)."""
    return SEX_TO_GENDER.get((sex or "").strip())


def to_sex(gender):
    """'female' → '여성'. 화면으로 되돌릴 때."""
    return GENDER_TO_SEX.get((gender or "").strip().lower(), "")


# ---------------------------------------------------------------------------
# 사용자 식별자 — 화면은 email, 백엔드는 id. 같은 값입니다.
# ---------------------------------------------------------------------------
# users.id 는 VARCHAR(100) 이지만 prescription_histories.user_id 가 VARCHAR(50)
# 입니다. 50자를 넘기면 그 사용자의 리포트 이력을 남길 수 없으므로 짧은 쪽에
# 맞춥니다.
MAX_USER_ID = 50


def to_user_id(email):
    """이메일을 로그인 아이디로. 대소문자·공백 때문에 같은 사람이 둘로
    갈리지 않도록 정규화합니다."""
    return str(email or "").strip().lower()[:MAX_USER_ID]


def to_session_user(data, fallback_email="", fallback_name=""):
    """에이전트 응답 → 화면이 기대하는 {name, email}.

    ★ id 와 email 을 모두 채웁니다. 한쪽만 주면 반대쪽을 보는 코드가
      조용히 빈 값을 받습니다.
    """
    au = (data or {}).get("user") or {}
    uid = to_user_id(au.get("id") or fallback_email)
    name = (au.get("name") or fallback_name or "").strip() or (uid.split("@")[0] if uid else "")
    return {"id": uid, "email": uid, "name": name}


# ---------------------------------------------------------------------------
# 숫자 — 화면은 전부 문자열로 보냅니다
# ---------------------------------------------------------------------------
def to_number(value, cast):
    """'45' → 45. 숫자로 안 읽히면 None.

    에이전트가 int/float 로 선언해 두었으므로, '58kg' 처럼 단위가 붙은 값을
    그대로 보내면 422 가 됩니다. 읽히지 않으면 아예 빼서 보내는 편이
    낫습니다 — 나이 한 칸 때문에 분석 전체가 막히면 안 됩니다.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return cast(float(text))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# 분석 입력 — 화면 AnalysisInput → 에이전트 recommend 폼
# ---------------------------------------------------------------------------
def to_recommend_form(state):
    """화면 입력을 에이전트 recommend 폼으로 옮깁니다. 규격은 §2.1.

    ※ 지금 에이전트는 name·birth_date·age·gender·weight_kg·file 여섯 개만
      선언해 두었고 exam·products·meds·chronic 은 받는 자리가 없습니다.
      그래도 **여기서는 보냅니다** — FastAPI 는 선언되지 않은 폼 필드를
      오류 없이 버립니다(실측: 넣은 응답과 뺀 응답의 html md5 가 동일).
      지금 보내도 무해하고, 에이전트가 Form 선언을 추가하는 순간 화면을
      고치지 않아도 곧바로 반영됩니다.

      반대로 '에이전트가 준비되면 그때 보낸다'로 두면, 준비된 날 이 파일을
      다시 고쳐야 하는데 그 사실을 아무도 기억하지 못합니다.
    """
    exam = state.get("exam") or {}
    form = {
        "name": state.get("name"),
        "age": to_number(state.get("age"), int),
        "gender": to_gender(state.get("sex")),
        "weight_kg": to_number(exam.get("weight"), float),
        # birth_date 는 화면이 수집하지 않습니다(state['date'] 는 검진일이라 다릅니다)
    }

    # 중첩 구조는 multipart 에 그대로 실을 수 없어 JSON 문자열 한 칸으로
    # 보냅니다(§2.2). 빈 값이면 키 자체를 빼는데, 빈 "{}" 를 보내면 받는
    # 쪽이 '입력했는데 비어 있다'로 읽기 때문입니다.
    for key, value in (("exam", exam),
                       ("products", state.get("products")),
                       ("meds", state.get("meds")),
                       ("chronic", state.get("chronic"))):
        if value:
            form[key] = json.dumps(value, ensure_ascii=False)
    return form


# ---------------------------------------------------------------------------
# 분석 결과 — 에이전트 리포트 → 화면 Report
# ---------------------------------------------------------------------------
# 에이전트가 완성된 html 만 주던 것을, 구조화된 값으로도 주기 시작하면
# 화면이 그 값으로 직접 그립니다(schema/api_contract.md §3.2 · §3.4).
# 화면 쪽 렌더러(renderReport 이하)는 이미 있으므로, 여기서 모양만
# 맞춰 주면 됩니다.
#
# ※ find_std 는 성분 코드를 화면 표기로 바꾸는 데만 씁니다.
#   에이전트가 'epa_dha' 로 부르는 것을 화면은 '오메가3' 로 부르는데,
#   그 대응표(alias)가 standards.py 에 이미 있어 그대로 씁니다.
#   손으로 표를 하나 더 만들면 한 글자만 달라도 조용히 어긋납니다.
from standards import find_std                                    # noqa: E402

# 에이전트 충족 상태 → 화면 섭취 수준. 화면 쪽 LEVEL 키와 같아야 합니다.
COVERAGE_TO_LEVEL = {
    "sufficient": "met",
    "deficient": "low",
    "excessive": "over",
}

# 값이 없을 때 렌더러가 터지지 않도록 두는 최소 형태.
# renderCard 가 n.bar.supp.toFixed(2) 와 n.sources.length 를 그대로 부르므로
# bar 는 반드시 숫자 네 칸, sources 는 반드시 배열이어야 합니다.
EMPTY_BAR = {"supp": 0.0, "meal": 0.0, "rdaMark": None, "ulMark": None}


def has_structured(data):
    """에이전트 응답에 구조화 리포트가 실려 있는지.

    이 판정 하나로 화면이 갈립니다 — 있으면 화면이 직접 그리고, 없으면
    지금까지처럼 에이전트가 만든 html 을 그대로 씁니다. 그래서 에이전트가
    아직 구버전이어도 화면이 멀쩡히 돕니다.
    """
    return bool((data or {}).get("calculated_target"))


def _nutrient_rows(data, local_by_name):
    """성분 카드 목록. 에이전트 값이 우선이고, 없는 칸만 로컬에서 빌립니다."""
    ri = (data.get("calculated_target") or {}).get("custom_ri") or {}
    cov = (data.get("coverage") or {}).get("coverage") or {}
    violations = {v.get("nutrient"): v
                  for v in (data.get("ul_check") or {}).get("ul_violations") or []}

    rows = []
    for code in sorted(set(ri) | set(cov)):
        std = find_std(code)
        name = std["name"] if std else code
        target = ri.get(code) or {}
        c = cov.get(code) or {}
        pct = c.get("pct")

        level = COVERAGE_TO_LEVEL.get(c.get("status"), "unknown")
        if code in violations:
            level = "over"          # 상한 초과가 충족 상태보다 우선입니다

        # 섭취 내역(영양제 얼마 · 식사 얼마)은 아직 에이전트가 주지 않습니다
        # (§3.2 갭 ①). 로컬 판정에 같은 성분이 있으면 그 내역을 빌려 오고,
        # 없으면 빈 막대로 둡니다 — 지어내지 않습니다.
        borrowed = local_by_name.get(name) or {}
        rows.append({
            "key": code,
            "name": name,
            "unit": target.get("unit") or borrowed.get("unit") or "",
            "level": level,
            "rda": target.get("value"),
            "ul": violations.get(code, {}).get("ul_limit") or borrowed.get("ul"),
            "hasStd": target.get("value") is not None,
            "supp": borrowed.get("supp", 0.0),
            "meal": borrowed.get("meal", 0.0),
            "total": borrowed.get("total", 0.0),
            "bar": borrowed.get("bar") or dict(EMPTY_BAR),
            "sources": borrowed.get("sources") or [],
            "unmapped": borrowed.get("unmapped") or [],
            "ulSuppOnly": borrowed.get("ulSuppOnly", False),
            "ulAmount": borrowed.get("ulAmount"),
            "gauge": {"rda": None if pct is None else round(pct / 100.0, 4),
                      "ul": borrowed.get("gauge", {}).get("ul")},
            "basis": _basis_text(target, violations.get(code)),
            "caption": borrowed.get("caption") or _caption_text(pct),
            "note": borrowed.get("note"),
        })
    return rows


def _basis_text(target, violation):
    parts = []
    if target.get("value") is not None:
        parts.append(f"권장 {_num(target['value'])}{target.get('unit', '')}")
    if violation:
        parts.append(f"상한 {_num(violation.get('ul_limit'))}")
    return " · ".join(parts)


def _caption_text(pct):
    if pct is None:
        return "권장량 정보 없음"
    return f"권장량의 {pct:.0f}% 충족"


def _num(v):
    """10.0 은 '10' 으로, 10.5 는 '10.5' 로. 화면에 .0 이 붙으면 지저분합니다."""
    if v is None:
        return ""
    return f"{v:g}"


def _issue_rows(data, local_issues):
    """점검 목록. 에이전트가 준 것을 먼저 싣고 로컬 판정을 덧붙입니다."""
    issues = []
    for v in (data.get("ul_check") or {}).get("ul_violations") or []:
        std = find_std(v.get("nutrient", ""))
        name = std["name"] if std else v.get("nutrient", "")
        issues.append({
            "kind": "상한 초과", "tone": "crit", "nut": name,
            "text": f"{name} 섭취 합계 {_num(v.get('total_intake'))}이(가) "
                    f"상한 {_num(v.get('ul_limit'))}을(를) 넘습니다.",
        })

    # cautions 는 아직 문자열 배열입니다(§3.2 갭 ②). 종류와 색을 알 수 없어
    # 일괄 '복용 안내'로 둡니다. 에이전트가 {kind,tone,med,text} 로 바꿔 주면
    # 아래 분기가 그대로 받습니다.
    for c in (data.get("timing_guidance") or {}).get("cautions") or []:
        if isinstance(c, dict):
            issues.append({"kind": c.get("kind") or "복용 안내",
                           "tone": c.get("tone") or "orange",
                           "med": c.get("med"), "text": c.get("text") or ""})
        else:
            issues.append({"kind": "복용 안내", "tone": "orange", "text": str(c)})

    # 약물 상호작용은 에이전트 응답에 없습니다. 로컬이 찾아낸 것을 버리면
    # 와파린을 적어 두고도 출혈 주의를 못 보게 됩니다 — 그쪽이 더 위험합니다.
    issues.extend(local_issues or [])
    return issues


def to_report_view(data, state, local=None):
    """에이전트 응답 data → 화면이 그리는 Report.

    local 은 화면 자체 판정 결과입니다. 에이전트가 아직 주지 않는 칸
    (섭취 내역·약물 상호작용·검진 판정)을 메우는 데만 씁니다. 에이전트가
    §3.2 의 갭을 채우면 이 인자를 빼고 부르면 됩니다.
    """
    local = local or {}
    local_by_name = {n.get("name"): n for n in local.get("nutrients") or []}

    nutrients = _nutrient_rows(data, local_by_name)
    issues = _issue_rows(data, local.get("issues"))

    worst, worst_rank = "met", -1
    rank = {"met": 0, "unknown": 1, "none": 2, "low": 3, "near": 4, "over": 5}
    for n in nutrients:
        if rank.get(n["level"], 0) > worst_rank:
            worst, worst_rank = n["level"], rank.get(n["level"], 0)

    return {
        "nutrients": nutrients,
        "issues": issues,
        # 검진 판정(A/B/D)은 에이전트가 만들지 않습니다(§3.2 갭 ③).
        # 국가 건강검진 실시기준으로 화면이 계산한 결과를 그대로 씁니다.
        "exam": local.get("exam") or {},
        "recommend": local.get("recommend"),
        "summary": local.get("summary"),
        "badges": local.get("badges") or [],
        "cols": local.get("cols") or 4,
        "worst": worst,
        "hasSupp": bool(nutrients),
        "mealOnly": not (state.get("products") or []),
        "input": state,
        "html": data.get("html") or "",
        "agentDisclaimer": data.get("disclaimer"),
        "partialFailure": bool(data.get("partial_failure")),
        # 화면이 어느 쪽으로 그릴지 고르는 표시입니다. nutrients 는 로컬
        # 판정에도 들어 있어 구분이 안 되므로, 따로 한 칸을 둡니다.
        "fromAgent": True,
        "meta": {"source": "agent", "engine": "agent + local(보완)"},
    }


# ---------------------------------------------------------------------------
# 응답 상태 — 에이전트는 봉투로 감싸서 돌려줍니다
# ---------------------------------------------------------------------------
SUCCESS = "success"
FAIL = "fail"
BLOCKED = "blocked"       # 가드레일 차단. 다시 시도해도 같은 결과입니다.


def looks_like_internal_error(message):
    """파이썬 예외가 문구로 새어 나온 경우인지.

    KeyError 는 str() 하면 따옴표만 붙은 "'pwd'" 로 나옵니다. 그대로
    사용자에게 보여 주면 무슨 말인지 알 수 없습니다.
    """
    m = (message or "").strip()
    return not m or (m.startswith("'") and m.endswith("'"))
