"""
exam.py — 건강검진 판정 (국가 건강검진 실시기준 [별표 4])
==============================================================================
app.js 의 EXAM 배열을 그대로 옮겨 온 것입니다. 화면과 서버가 같은 key 를
써야 하므로, 항목을 바꿀 때는 **양쪽을 함께** 고쳐야 합니다.

    화면 : src/app.js 의 EXAM 배열   →  고친 뒤 node build-live.js
    서버 : 이 파일의 EXAM            →  고친 뒤 서버 재시작

한 항목이 하는 일이 셋입니다.
    inputs  입력칸을 만듭니다 (화면 전용. 서버는 쓰지 않습니다)
    ref     표의 '판정 기준' 칸에 들어갈 문구
    show    표의 '내 수치' 칸에 들어갈 문구
    judge   A(정상A) · B(경계) · D(질환의심) · ''(미입력) 판정

판정 코드는 [별표 4] 및 [별표 4의 별첨] 검사항목별 판정기준을 따릅니다.
성분 기준값(standards.py)과 달리 이쪽은 고시를 옮긴 것이지만, 고시가
개정되면 여기도 함께 고쳐야 합니다.
==============================================================================
"""

from typing import Optional

# -----------------------------------------------------------------------------
# 판정 코드
# -----------------------------------------------------------------------------
_JUDGE = {
    "A": {"code": "A", "text": "정상A",    "tone": "green"},
    "B": {"code": "B", "text": "경계",     "tone": "orange"},
    "D": {"code": "D", "text": "질환의심", "tone": "red"},
    "N": {"code": "",  "text": "미입력",   "tone": "gray"},
}


def J(code: str, text: Optional[str] = None, advice: Optional[str] = None) -> dict:
    """판정 하나를 만듭니다. text 를 주면 기본 문구 대신 그 문구를 씁니다.

    advice 를 붙이면 리포트 요약에 강조 안내로 나옵니다.
    ※ 매번 새 dict 를 돌려줍니다 — 같은 객체를 돌려주면 한 항목에 붙인
      advice 가 다른 항목까지 따라다닙니다.
    """
    j = dict(_JUDGE[code])
    if text:
        j["text"] = text
    if advice:
        j["advice"] = advice
    return j


def num(v):
    """숫자로 읽습니다. 빈 값이나 숫자가 아니면 None.

    화면이 보내는 값은 전부 문자열입니다("45"). 그래서 여기서 한 번
    걸러 주고, 이후 계산은 None 여부만 보면 됩니다.
    """
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def is_male(ctx) -> bool:
    return (ctx or {}).get("sex") == "남성"


def bmi_of(v) -> Optional[float]:
    """키·몸무게로 BMI 를 계산합니다. 둘 중 하나라도 없으면 None."""
    h, w = num(v.get("height")), num(v.get("weight"))
    if not h or not w:
        return None
    return w / ((h / 100) ** 2)


def _s(v, key) -> str:
    """선택형 항목의 값. 고르지 않았으면 빈 문자열."""
    return v.get(key) or ""


# =============================================================================
# 항목별 판정 함수
# -----------------------------------------------------------------------------
# 이름은 _judge_<항목key> 입니다. 아래 EXAM 에서 참조합니다.
# =============================================================================

def _judge_cxr(v, ctx):
    x = _s(v, "cxr")
    if not x:
        return J("N")
    if x == "정상":
        return J("A")
    if x == "비활동성 폐결핵":
        return J("B")
    return J("D")


def _judge_bp(v, ctx):
    s, d = num(v.get("sbp")), num(v.get("dbp"))
    if s is None or d is None:
        return J("N")
    if s >= 140 or d >= 90:      # 140 이상 또는 90 이상
        return J("D")
    if s < 120 and d < 80:       # 120 미만 이며 80 미만
        return J("A")
    return J("B")                # 120-139 또는 80-89


def _judge_bmi(v, ctx):
    b = bmi_of(v)
    if b is None:
        return J("N")
    if b < 18.5 or b >= 30:
        return J("D")
    if b <= 24.9:
        return J("A")
    return J("B")                # 25 ~ 29.9


def _judge_waist(v, ctx):
    w = num(v.get("waist"))
    if w is None:
        return J("N")
    # 허리둘레는 기준표에 질환의심 구분이 없습니다.
    return J("A") if w < (90 if is_male(ctx) else 85) else J("B")


def _judge_hb(v, ctx):
    h = num(v.get("hb"))
    if h is None:
        return J("N")
    if is_male(ctx):
        if h < 12.0:
            return J("D")
        if h < 13.0:
            return J("B")
        # 상한 초과는 기준표에 없어 경계로 둡니다
        return J("A") if h <= 16.5 else J("B")
    if h < 10.0:
        return J("D")
    if h < 12.0:
        return J("B")
    return J("A") if h <= 15.5 else J("B")


def _judge_glu(v, ctx):
    g = num(v.get("glu"))
    if g is None:
        return J("N")
    return J("D") if g >= 126 else (J("B") if g >= 100 else J("A"))


def _cut(key, d_at, b_at):
    """'값이 d_at 이상이면 질환의심, b_at 이상이면 경계' 형태의 흔한 판정."""
    def f(v, ctx):
        x = num(v.get(key))
        if x is None:
            return J("N")
        return J("D") if x >= d_at else (J("B") if x >= b_at else J("A"))
    return f


def _judge_hdl(v, ctx):
    x = num(v.get("hdl"))
    if x is None:
        return J("N")
    return J("D") if x < 40 else (J("B") if x < 60 else J("A"))


def _judge_ggt(v, ctx):
    x = num(v.get("ggt"))
    if x is None:
        return J("N")
    if is_male(ctx):
        if x >= 78:
            return J("D")
        if x >= 64:
            return J("B")
        return J("A") if x >= 11 else J("B")
    if x >= 46:
        return J("D")
    if x >= 36:
        return J("B")
    return J("A") if x >= 8 else J("B")


def _judge_upro(v, ctx):
    x = _s(v, "upro")
    if not x:
        return J("N")
    if x == "음성(-)":
        return J("A")
    if x == "약양성(±)":
        return J("B")
    return J("D")


def _judge_cr(v, ctx):
    x = num(v.get("cr"))
    if x is None:
        return J("N")
    return J("D") if x > 1.5 else J("A")


def _judge_egfr(v, ctx):
    x = num(v.get("egfr"))
    if x is None:
        return J("N")
    return J("D") if x < 60 else J("A")


def _judge_tscore(v, ctx):
    x = num(v.get("tscore"))
    if x is None:
        return J("N")
    if x <= -2.5:
        return J("D")
    return J("A") if x >= -1 else J("B")


def _judge_bmd(v, ctx):
    x = num(v.get("bmd"))
    if x is None:
        return J("N")
    if x < 80:
        return J("D")
    return J("A") if x > 120 else J("B")


def _judge_leg(v, ctx):
    x = num(v.get("leg"))
    if x is None:
        return J("N")
    return J("D") if x >= 20 else (J("B") if x > 10 else J("A"))


def _judge_balC(v, ctx):
    x = num(v.get("balC"))
    if x is None:
        return J("N")
    return J("D") if x <= 5 else (J("B") if x < 15 else J("A"))


def _judge_balO(v, ctx):
    x = num(v.get("balO"))
    if x is None:
        return J("N")
    return J("D") if x <= 9 else (J("B") if x < 20 else J("A"))


_CARE = "가까운 정신건강의학과나 지역 정신건강복지센터에서 상담받아 보시기를 권합니다."


def _judge_phq9(v, ctx):
    x = num(v.get("phq9"))
    if x is None:
        return J("N")
    # 9번 문항(자살 사고)은 총점과 상관없이 심한 쪽으로 올립니다.
    if x >= 20 or _s(v, "phq9q9") == "1점 이상":
        return J("D", "심한 우울증 의심",
                 advice="되도록 빠른 시일 안에 전문가와 상담하시기 바랍니다. " + _CARE)
    if x >= 10:
        return J("D", "중간정도 우울증 의심", advice=_CARE)
    if x >= 5:
        return J("B", "가벼운 우울증상")
    return J("A", "우울증상 없음")


def _judge_cape(v, ctx):
    f, d = num(v.get("capeF")), num(v.get("capeD"))
    if f is None and d is None:
        return J("N")
    if (f or 0) >= 6 or (d or 0) >= 6:
        return J("D", "전문의 진단 필요",
                 advice="정신건강의학과 전문의의 진단이 필요한 결과입니다.")
    return J("A", "특이소견 없음")


def _judge_kdsq(v, ctx):
    x = num(v.get("kdsq"))
    if x is None:
        return J("N")
    if x >= 6:
        return J("D", "인지기능 저하 의심",
                 advice="치매안심센터나 신경과 진료를 통한 정밀검사를 권합니다.")
    return J("A", "특이소견 없음")


def _judge_pta(v, ctx):
    x = num(v.get("pta"))
    if x is None:
        return J("N")
    return J("D", "질환의심") if x >= 40 else J("A", "정상")


def _judge_whisper(v, ctx):
    x = _s(v, "whisper")
    if not x:
        return J("N")
    return J("A", "정상") if x == "양쪽 3개 이상 정확" else J("D", "정밀검사 의뢰")


def _judge_spiro(v, ctx):
    r, e, f = num(v.get("ratio")), num(v.get("fev1")), num(v.get("fvc"))
    if r is None:
        return J("N")
    if r < 70:
        return J("D", "COPD 의심")
    if (e is not None and e < 80) or (f is not None and f < 80):
        return J("B", "기타 폐기능 이상")
    return J("A")


def _oral_yesno(key, bad_code, bad_text):
    """구강 항목 — '없음'이면 양호, '있음'이면 정해진 판정."""
    def f(v, ctx):
        x = _s(v, key)
        if not x:
            return J("N")
        return J("A", "양호") if x == "없음" else J(bad_code, bad_text)
    return f


def _oral_grade(key):
    """치은염증·치석 — 없음 / 경증 / 중증."""
    def f(v, ctx):
        x = _s(v, key)
        if not x:
            return J("N")
        if x == "없음":
            return J("A", "양호")
        return J("D", "질환의심") if x == "경증" else J("D", "치료필요")
    return f


def _judge_plaque(v, ctx):
    x = num(v.get("plaque"))
    if x is None:
        return J("N")
    return J("D", "개선요망") if x >= 3 else (J("B", "보통") if x >= 1 else J("A", "우수"))


# =============================================================================
# 검진 항목 EXAM
# -----------------------------------------------------------------------------
# 여기 배열의 순서가 그대로 리포트 표의 구분줄 순서입니다.
# =============================================================================
def _unit_show(key, unit):
    """'132 mmHg' 처럼 값 뒤에 단위를 붙여 보여 줍니다. 없으면 '—'."""
    def f(v, ctx=None):
        return "—" if num(v.get(key)) is None else f"{v.get(key)} {unit}"
    return f


EXAM = [
    {"group": "폐결핵·기타흉부질환", "items": [
        {"key": "cxr", "name": "흉부방사선촬영",
         "inputs": [{"key": "cxr", "type": "select",
                     "options": ["", "정상", "비활동성 폐결핵", "그 외 소견"]}],
         "ref": lambda ctx: "정상",
         "show": lambda v, ctx=None: _s(v, "cxr") or "—",
         "judge": _judge_cxr},
    ]},

    {"group": "고혈압", "items": [
        {"key": "bp", "name": "혈압",
         "inputs": [{"key": "sbp", "name": "수축기", "unit": "mmHg"},
                    {"key": "dbp", "name": "이완기", "unit": "mmHg"}],
         "ref": lambda ctx: "120/80 미만",
         "show": lambda v, ctx=None: (
             "—" if (num(v.get("sbp")) is None and num(v.get("dbp")) is None)
             else f"{v.get('sbp') or '—'}/{v.get('dbp') or '—'}"),
         "judge": _judge_bp},
    ]},

    {"group": "비만", "items": [
        {"key": "bmi", "name": "체질량지수(BMI)",
         "inputs": [{"key": "height", "name": "키", "unit": "cm"},
                    {"key": "weight", "name": "몸무게", "unit": "kg"}],
         "ref": lambda ctx: "18.5~24.9",
         "show": lambda v, ctx=None: (
             "—" if bmi_of(v) is None else f"{bmi_of(v):.1f} kg/m²"),
         "judge": _judge_bmi},
        {"key": "waist", "name": "허리둘레",
         "inputs": [{"key": "waist", "unit": "cm"}],
         "ref": lambda ctx: "90 미만" if is_male(ctx) else "85 미만",
         "show": _unit_show("waist", "cm"),
         "judge": _judge_waist},
    ]},

    {"group": "빈혈", "items": [
        {"key": "hb", "name": "혈색소",
         "inputs": [{"key": "hb", "unit": "g/dL"}],
         "ref": lambda ctx: "13.0~16.5" if is_male(ctx) else "12.0~15.5",
         "show": _unit_show("hb", "g/dL"),
         "judge": _judge_hb},
    ]},

    {"group": "당뇨병", "items": [
        {"key": "glu", "name": "공복혈당",
         "inputs": [{"key": "glu", "unit": "mg/dL"}],
         "ref": lambda ctx: "100 미만",
         "show": _unit_show("glu", "mg/dL"),
         "judge": _judge_glu},
    ]},

    {"group": "이상지질혈증", "items": [
        {"key": "tc", "name": "총콜레스테롤",
         "inputs": [{"key": "tc", "unit": "mg/dL"}],
         "ref": lambda ctx: "200 미만",
         "show": _unit_show("tc", "mg/dL"),
         "judge": _cut("tc", 240, 200)},
        {"key": "hdl", "name": "HDL 콜레스테롤",
         "inputs": [{"key": "hdl", "unit": "mg/dL"}],
         "ref": lambda ctx: "60 이상",
         "show": _unit_show("hdl", "mg/dL"),
         "judge": _judge_hdl},
        {"key": "tg", "name": "중성지방",
         "inputs": [{"key": "tg", "unit": "mg/dL"}],
         "ref": lambda ctx: "150 미만",
         "show": _unit_show("tg", "mg/dL"),
         "judge": _cut("tg", 200, 150)},
        {"key": "ldl", "name": "LDL 콜레스테롤",
         "inputs": [{"key": "ldl", "unit": "mg/dL"}],
         "ref": lambda ctx: "130 미만",
         "show": _unit_show("ldl", "mg/dL"),
         "judge": _cut("ldl", 160, 130)},
    ]},

    {"group": "간장질환", "items": [
        {"key": "ast", "name": "AST(SGOT)",
         "inputs": [{"key": "ast", "unit": "U/L"}],
         "ref": lambda ctx: "40 이하",
         "show": _unit_show("ast", "U/L"),
         "judge": _cut("ast", 51, 41)},
        {"key": "alt", "name": "ALT(SGPT)",
         "inputs": [{"key": "alt", "unit": "U/L"}],
         "ref": lambda ctx: "35 이하",
         "show": _unit_show("alt", "U/L"),
         "judge": _cut("alt", 46, 36)},
        {"key": "ggt", "name": "γ-GTP",
         "inputs": [{"key": "ggt", "unit": "U/L"}],
         "ref": lambda ctx: "11~63" if is_male(ctx) else "8~35",
         "show": _unit_show("ggt", "U/L"),
         "judge": _judge_ggt},
    ]},

    {"group": "신장질환", "items": [
        {"key": "upro", "name": "요단백",
         "inputs": [{"key": "upro", "type": "select",
                     "options": ["", "음성(-)", "약양성(±)", "양성(+1) 이상"]}],
         "ref": lambda ctx: "음성(-)",
         "show": lambda v, ctx=None: _s(v, "upro") or "—",
         "judge": _judge_upro},
        {"key": "cr", "name": "혈청크레아티닌",
         "inputs": [{"key": "cr", "unit": "mg/dL"}],
         "ref": lambda ctx: "1.5 이하",
         "show": _unit_show("cr", "mg/dL"),
         "judge": _judge_cr},
        {"key": "egfr", "name": "신사구체여과율(e-GFR)",
         "inputs": [{"key": "egfr", "unit": "mL/min"}],
         "ref": lambda ctx: "60 이상",
         "show": lambda v, ctx=None: (
             "—" if num(v.get("egfr")) is None else f"{v.get('egfr')} mL/min/1.73m²"),
         "judge": _judge_egfr},
    ]},

    {"group": "골다공증", "items": [
        {"key": "tscore", "name": "골밀도 T-score",
         "inputs": [{"key": "tscore", "unit": "T"}],
         "ref": lambda ctx: "-1 이상",
         "show": lambda v, ctx=None: (
             "—" if num(v.get("tscore")) is None else f"{v.get('tscore')}"),
         "judge": _judge_tscore},
        {"key": "bmd", "name": "골밀도(정량)",
         "inputs": [{"key": "bmd", "unit": "mg/㎤"}],
         "ref": lambda ctx: "120 초과",
         "show": _unit_show("bmd", "mg/㎤"),
         "judge": _judge_bmd},
    ]},

    {"group": "노인 신체기능", "items": [
        {"key": "leg", "name": "하지기능",
         "inputs": [{"key": "leg", "unit": "초"}],
         "ref": lambda ctx: "10초 이내",
         "show": lambda v, ctx=None: "—" if num(v.get("leg")) is None else f"{v.get('leg')}초",
         "judge": _judge_leg},
        {"key": "balC", "name": "평형성(눈 감은 상태)",
         "inputs": [{"key": "balC", "unit": "초"}],
         "ref": lambda ctx: "15초 이상",
         "show": lambda v, ctx=None: "—" if num(v.get("balC")) is None else f"{v.get('balC')}초",
         "judge": _judge_balC},
        {"key": "balO", "name": "평형성(눈 뜬 상태)",
         "inputs": [{"key": "balO", "unit": "초"}],
         "ref": lambda ctx: "20초 이상",
         "show": lambda v, ctx=None: "—" if num(v.get("balO")) is None else f"{v.get('balO')}초",
         "judge": _judge_balO},
    ]},

    {"group": "정신건강·인지", "items": [
        {"key": "phq9", "name": "우울증(PHQ-9)",
         "inputs": [{"key": "phq9", "name": "총점", "unit": "점"},
                    {"key": "phq9q9", "type": "select", "name": "9번 문항",
                     "options": ["", "0점", "1점 이상"]}],
         "ref": lambda ctx: "0~4점",
         "show": lambda v, ctx=None: "—" if num(v.get("phq9")) is None else f"{v.get('phq9')}점",
         "judge": _judge_phq9},
        {"key": "cape", "name": "조기정신증(CAPE-15)",
         "inputs": [{"key": "capeF", "name": "빈도 총점", "unit": "점"},
                    {"key": "capeD", "name": "고통 총점", "unit": "점"}],
         "ref": lambda ctx: "각 0~5점",
         "show": lambda v, ctx=None: (
             "—" if (num(v.get("capeF")) is None and num(v.get("capeD")) is None)
             else f"빈도 {v.get('capeF') or '—'} · 고통 {v.get('capeD') or '—'}"),
         "judge": _judge_cape},
        {"key": "kdsq", "name": "인지기능(KDSQ-C)",
         "inputs": [{"key": "kdsq", "unit": "점"}],
         "ref": lambda ctx: "0~5점",
         "show": lambda v, ctx=None: "—" if num(v.get("kdsq")) is None else f"{v.get('kdsq')}점",
         "judge": _judge_kdsq},
    ]},

    {"group": "청력", "items": [
        {"key": "pta", "name": "순음청력검사",
         "inputs": [{"key": "pta", "unit": "dB"}],
         "ref": lambda ctx: "40dB 미만",
         "show": _unit_show("pta", "dB"),
         "judge": _judge_pta},
        {"key": "whisper", "name": "귓속말 검사",
         "inputs": [{"key": "whisper", "type": "select",
                     "options": ["", "양쪽 3개 이상 정확", "한쪽이라도 3개 미만"]}],
         "ref": lambda ctx: "양쪽 3개 이상",
         "show": lambda v, ctx=None: _s(v, "whisper") or "—",
         "judge": _judge_whisper},
    ]},

    {"group": "만성폐쇄성폐질환", "items": [
        {"key": "spiro", "name": "폐기능검사",
         "inputs": [{"key": "ratio", "name": "FEV1/FVC", "unit": "%"},
                    {"key": "fev1", "name": "FEV1", "unit": "%"},
                    {"key": "fvc", "name": "FVC", "unit": "%"}],
         "ref": lambda ctx: "FEV1/FVC 70 이상",
         "show": lambda v, ctx=None: (
             "—" if num(v.get("ratio")) is None else f"FEV1/FVC {v.get('ratio')}%"),
         "judge": _judge_spiro},
    ]},

    {"group": "구강", "items": [
        {"key": "caries", "name": "우식치아",
         "inputs": [{"key": "caries", "type": "select", "options": ["", "없음", "있음"]}],
         "ref": lambda ctx: "없음",
         "show": lambda v, ctx=None: _s(v, "caries") or "—",
         "judge": _oral_yesno("caries", "D", "치료필요")},
        {"key": "suspect", "name": "우식의심치아",
         "inputs": [{"key": "suspect", "type": "select", "options": ["", "없음", "있음"]}],
         "ref": lambda ctx: "없음",
         "show": lambda v, ctx=None: _s(v, "suspect") or "—",
         "judge": _oral_yesno("suspect", "D", "질환의심")},
        {"key": "filled", "name": "수복치아",
         "inputs": [{"key": "filled", "type": "select", "options": ["", "없음", "있음"]}],
         "ref": lambda ctx: "없음",
         "show": lambda v, ctx=None: _s(v, "filled") or "—",
         "judge": _oral_yesno("filled", "B", "주의")},
        {"key": "lost", "name": "상실치아",
         "inputs": [{"key": "lost", "type": "select", "options": ["", "없음", "있음"]}],
         "ref": lambda ctx: "없음",
         "show": lambda v, ctx=None: _s(v, "lost") or "—",
         "judge": _oral_yesno("lost", "D", "치료필요")},
        {"key": "gingiva", "name": "치은염증",
         "inputs": [{"key": "gingiva", "type": "select", "options": ["", "없음", "경증", "중증"]}],
         "ref": lambda ctx: "없음",
         "show": lambda v, ctx=None: _s(v, "gingiva") or "—",
         "judge": _oral_grade("gingiva")},
        {"key": "calculus", "name": "치석",
         "inputs": [{"key": "calculus", "type": "select", "options": ["", "없음", "경증", "중증"]}],
         "ref": lambda ctx: "없음",
         "show": lambda v, ctx=None: _s(v, "calculus") or "—",
         "judge": _oral_grade("calculus")},
        {"key": "plaque", "name": "치면세균막검사",
         "inputs": [{"key": "plaque", "unit": "점"}],
         "ref": lambda ctx: "1점 미만",
         "show": lambda v, ctx=None: "—" if num(v.get("plaque")) is None else f"{v.get('plaque')}점",
         "judge": _judge_plaque},
    ]},
]


# 어떤 항목이 고혈압·당뇨병·이상지질혈증에 속하는지 (종합 판정 구분에 필요)
HTN_DM_LIPID = ["bp", "glu", "tc", "hdl", "tg", "ldl"]


def compute_exam(state: dict) -> dict:
    """Input 의 exam·chronic 을 읽어 Report.exam 을 만듭니다.

    돌려주는 모양은 '백엔드 연동 규격서' §5.2 그대로입니다.
    """
    ctx = {"sex": state.get("sex"), "age": num(state.get("age"))}
    values = state.get("exam") or {}

    groups = []
    for g in EXAM:
        rows = []
        for it in g["items"]:
            rows.append({
                "key":   it["key"],
                "name":  it["name"],
                "ref":   it["ref"](ctx),
                "value": it["show"](values, ctx),
                "judge": it["judge"](values, ctx),
            })
        groups.append({"group": g["group"], "rows": rows})

    rows = [r for g in groups for r in g["rows"]]

    counts = {"A": 0, "B": 0, "D": 0}
    for r in rows:
        code = r["judge"]["code"]
        if code:
            counts[code] += 1

    # -------------------------------------------------------------------------
    # 별표 4 첫 표의 종합 판정 구분
    # 순서가 중요합니다 — 위에서부터 먼저 걸리는 것이 이깁니다.
    # -------------------------------------------------------------------------
    d_rows = [r for r in rows if r["judge"]["code"] == "D"]
    is_meta = any(r["key"] in HTN_DM_LIPID for r in d_rows)
    chronic = state.get("chronic") or []

    if chronic:
        overall = {"label": "유질환자", "tone": "red",
                   "desc": f"{' · '.join(chronic)} 진단 후 약물 치료 중으로 입력되었습니다."}
    elif is_meta:
        overall = {"label": "고혈압·당뇨병·이상지질혈증 질환의심", "tone": "red",
                   "desc": "해당 항목이 기준을 벗어나 진료와 검사가 필요합니다."}
    elif d_rows:
        overall = {"label": "일반 질환의심", "tone": "red",
                   "desc": "추적검사나 전문 의료기관의 정확한 진단이 필요합니다."}
    elif counts["B"]:
        overall = {"label": "정상B(경계)", "tone": "orange",
                   "desc": "건강에 이상은 없으나 식생활습관 개선 등 자가관리가 필요합니다."}
    elif counts["A"]:
        overall = {"label": "정상A", "tone": "green", "desc": "검진 결과 건강이 양호합니다."}
    else:
        overall = {"label": "미입력", "tone": "gray",
                   "desc": "검진 결과를 입력하면 종합 판정을 계산합니다."}

    return {
        "groups": groups,
        "rows": rows,
        "counts": counts,
        "overall": overall,
        "filled": counts["A"] + counts["B"] + counts["D"],
        "abnormal": [r for r in rows if r["judge"]["code"] in ("D", "B")],
    }
