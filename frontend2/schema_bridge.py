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

대응 관계의 근거는 schema/matrix.md 이고, 필드 정의는
agent/schemas/models.py 와 같은 값을 씁니다.
"""

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
    """화면 입력에서 에이전트가 받는 필드만 뽑아 냅니다.

    ※ 지금 에이전트 recommend 는 name·birth_date·age·gender·weight_kg·file
      여섯 개만 받습니다. 영양제(products)·복용약(meds)·검진수치(exam)를
      실을 자리가 없어서 여기서 사라집니다. 측정해 보니 입력의 79~86%가
      전달되지 않습니다(qa/results/coverage.md).
      에이전트에 필드가 늘어나면 이 함수만 고치면 됩니다.
    """
    exam = state.get("exam") or {}
    return {
        "name": state.get("name"),
        "age": to_number(state.get("age"), int),
        "gender": to_gender(state.get("sex")),
        "weight_kg": to_number(exam.get("weight"), float),
        # birth_date 는 화면이 수집하지 않습니다(state['date'] 는 검진일이라 다릅니다)
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
