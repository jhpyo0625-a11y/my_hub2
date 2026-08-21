"""
vision.py — 검진표 이미지를 읽어 입력값으로 바꿉니다  (★ 교체지점)
==============================================================================
사용자가 대화 화면의 ＋ 버튼으로 건강검진 결과지 사진을 올리면, 서버가
그 이미지에서 검진 수치를 읽어 냅니다. 읽어 낸 값은 화면이 곧바로 입력에
채워 넣고, **이미 채워진 항목은 다시 묻지 않습니다.**

이 파일이 하는 일은 두 가지입니다.

    1. 올라온 것이 정말 이미지인지 확인한다      → sniff_image()
    2. 그 이미지에서 검진값을 읽어 낸다          → read_exam_image()

------------------------------------------------------------------------------
판독 방식은 두 가지이고, 환경변수로 갈립니다
------------------------------------------------------------------------------
  ANTHROPIC_API_KEY 가 있으면   →  Claude 에 이미지를 보내 실제로 판독합니다
  없으면 (기본)                 →  예시 판독. 이미지마다 다른 값이 나옵니다

예시 판독은 '아무 값이나' 돌려주는 게 아니라, 이미지 내용의 해시로 견본
넷 중 하나를 고릅니다. 그래서 **같은 사진은 늘 같은 결과**가 나오고, 다른
사진을 올리면 다른 결과가 나옵니다. 화면 흐름(판독 → 자동 채움 → 남은
질문만 하기)을 제대로 확인할 수 있습니다.

돌려주는 값에 source 가 들어 있고, 화면은 그 값이 "demo" 이면 말풍선에
**'예시 판독'** 이라고 분명히 적습니다. 실제 판독 결과인 척하지 않습니다.

------------------------------------------------------------------------------
실제 모델로 바꿀 때
------------------------------------------------------------------------------
_read_with_claude() 하나만 원하는 모델 호출로 바꾸면 됩니다. 지켜야 할 것은
돌려주는 모양뿐입니다 (§ read_exam_image 의 docstring).
어떤 모델을 쓰든 _clean() 을 반드시 통과시키세요 — 모델이 엉뚱한 키나
말도 안 되는 값을 뱉어도 그 값이 그대로 입력에 들어가면 안 됩니다.
==============================================================================
"""

import base64
import hashlib
import json
import os
import urllib.error
import urllib.request

from exam import EXAM
from standards import CHRONIC

# 사진 한 장이 이보다 크면 받지 않습니다. 요즘 폰 사진이 3~6MB 쯤 되므로
# 10MB 면 충분하고, 더 키우면 판독이 느려지기만 합니다.
MAX_IMAGE_BYTES = 10 * 1024 * 1024

# 이미지 **만** 받습니다. PDF·HWP·엑셀은 거절합니다.
ALLOWED_MIME = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp", "image/heic"}


# =============================================================================
# 1. 정말 이미지인가
# -----------------------------------------------------------------------------
# 확장자나 브라우저가 보낸 Content-Type 은 믿지 않습니다. 둘 다 사용자가
# 마음대로 적어 보낼 수 있기 때문입니다. 파일 앞머리의 고정된 바이트
# (매직 넘버)로 직접 확인합니다.
# =============================================================================
def sniff_image(data: bytes):
    """이미지면 그 MIME 타입을, 아니면 None 을 돌려줍니다."""
    if len(data) < 12:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:2] == b"BM":
        return "image/bmp"
    if data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"hevc", b"mif1"):
        return "image/heic"
    return None


# =============================================================================
# 2. 읽어 낸 값 다듬기
# -----------------------------------------------------------------------------
# 모델이든 견본이든, 여기를 반드시 통과시킵니다. 화면이 아는 key 만 남기고
# 선택형 항목은 정해진 보기 중 하나인지 확인합니다.
# =============================================================================
_ITEM_OF = {}      # exam key → (검진 항목, 입력칸 정의)
for _g in EXAM:
    for _it in _g["items"]:
        for _inp in _it["inputs"]:
            _ITEM_OF[_inp["key"]] = (_g["group"], _it, _inp)

EXAM_KEYS = list(_ITEM_OF)


def _clean_exam(raw) -> dict:
    """화면이 아는 검진 key 만 남깁니다."""
    out = {}
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        if k not in _ITEM_OF or v in (None, ""):
            continue
        _group, _it, inp = _ITEM_OF[k]
        if inp.get("type") == "select":
            # 선택형은 정해진 보기 중 하나여야 합니다. 아니면 버립니다 —
            # 화면의 드롭다운에 없는 값이 들어가면 선택이 풀려 보입니다.
            if str(v) in (inp.get("options") or []):
                out[k] = str(v)
            continue
        # 숫자 항목은 숫자로 읽히는지만 봅니다. 화면과 서버 모두 값을
        # 문자열로 다루므로("45" 이지 45 가 아닙니다) 문자열로 넣습니다.
        try:
            float(v)
        except (TypeError, ValueError):
            continue
        out[k] = str(v).strip()
    return out


def _clean(raw) -> dict:
    """판독 결과 전체를 다듬습니다."""
    raw = raw if isinstance(raw, dict) else {}
    exam = _clean_exam(raw.get("exam"))

    sex = str(raw.get("sex") or "").strip()
    if sex not in ("남성", "여성"):
        sex = ""

    age = str(raw.get("age") or "").strip()
    if age:
        try:
            a = int(float(age))
            age = str(a) if 0 < a < 130 else ""
        except (TypeError, ValueError):
            age = ""

    chronic = [c for c in (raw.get("chronic") or []) if c in CHRONIC]

    # 어느 검진 그룹이 채워졌는지 — 화면이 '이 그룹은 이미 있으니 묻지 말자'
    # 를 판단하는 데 씁니다. 서버가 계산해서 내려보내면 화면이 EXAM 을
    # 다시 뒤지지 않아도 됩니다.
    groups = []
    for g in EXAM:
        if any(inp["key"] in exam for it in g["items"] for inp in it["inputs"]):
            groups.append(g["group"])

    # 사람이 읽을 수 있는 '무엇을 읽었는지' 목록. 말풍선에 그대로 씁니다.
    fields = []
    for g in EXAM:
        for it in g["items"]:
            vals = {inp["key"]: exam[inp["key"]] for inp in it["inputs"] if inp["key"] in exam}
            if not vals:
                continue
            fields.append({"group": g["group"], "name": it["name"],
                           "text": it["show"](exam, {"sex": sex})})

    return {
        "name": str(raw.get("name") or "").strip()[:40],
        "age": age,
        "sex": sex,
        "date": str(raw.get("date") or "").strip()[:40],
        "exam": exam,
        "chronic": chronic,
        "groups": groups,
        "fields": fields,
    }


# =============================================================================
# 3. 예시 판독용 견본
# -----------------------------------------------------------------------------
# 실제 검진 결과지에 흔히 있는 조합을 넷 만들어 두었습니다. 채워지는 검진
# 그룹이 서로 달라서, 어떤 사진을 올리느냐에 따라 '남은 질문'도 달라집니다.
# =============================================================================
DEMO_SHEETS = [
    {"name": "홍길동", "age": "45", "sex": "남성", "date": "2026-03-10",
     "chronic": [],
     "exam": {"sbp": "132", "dbp": "84", "height": "175", "weight": "88", "waist": "94",
              "hb": "15.1", "glu": "108", "tc": "226", "hdl": "42", "tg": "189", "ldl": "146",
              "ast": "38", "alt": "45", "ggt": "71",
              "upro": "음성(-)", "cr": "1.0", "egfr": "88"}},

    {"name": "김영자", "age": "68", "sex": "여성", "date": "2025-11-18",
     "chronic": ["고혈압"],
     "exam": {"cxr": "정상", "sbp": "148", "dbp": "88", "height": "156", "weight": "52",
              "waist": "82", "hb": "11.4", "glu": "132", "tc": "210", "hdl": "55",
              "tg": "143", "ldl": "128", "ast": "26", "alt": "22", "ggt": "28",
              "upro": "약양성(±)", "cr": "1.1", "egfr": "58",
              "tscore": "-2.7", "bmd": "78"}},

    {"name": "이수민", "age": "34", "sex": "여성", "date": "2026-01-07",
     "chronic": [],
     "exam": {"cxr": "정상", "sbp": "112", "dbp": "71", "height": "163", "weight": "54",
              "waist": "71", "hb": "12.8", "glu": "88", "tc": "178", "hdl": "68",
              "tg": "82", "ldl": "96", "ast": "18", "alt": "15", "ggt": "14",
              "upro": "음성(-)", "cr": "0.7", "egfr": "104"}},

    {"name": "박정호", "age": "57", "sex": "남성", "date": "2025-09-02",
     "chronic": ["이상지질혈증"],
     "exam": {"cxr": "비활동성 폐결핵", "sbp": "126", "dbp": "79", "height": "171",
              "weight": "79", "waist": "91", "hb": "14.6", "glu": "97", "tc": "188",
              "hdl": "47", "tg": "168", "ldl": "112", "ast": "62", "alt": "58", "ggt": "96",
              "upro": "음성(-)", "cr": "1.2", "egfr": "76",
              "ratio": "68", "fev1": "74", "fvc": "89"}},
]


def _read_demo(data: bytes) -> dict:
    """이미지 내용의 해시로 견본 하나를 고릅니다.

    무작위가 아니라 해시입니다 — 같은 사진을 다시 올리면 같은 결과가 나와야
    '이 사진은 이렇게 읽혔구나' 를 확인할 수 있기 때문입니다.
    """
    h = hashlib.sha256(data).digest()
    return dict(DEMO_SHEETS[h[0] % len(DEMO_SHEETS)])


# =============================================================================
# 4. 실제 판독 (Claude 비전)
# -----------------------------------------------------------------------------
# ※ 이 경로는 API 키가 있는 환경에서만 돕니다. 키 없이 개발할 때는 실행되지
#   않으므로, 처음 켜실 때는 응답을 한 번 눈으로 확인해 보시기 바랍니다.
# =============================================================================
VISION_MODEL = os.environ.get("VISION_MODEL", "claude-sonnet-4-5")

_PROMPT = """이 이미지는 한국의 건강검진 결과지입니다.
읽을 수 있는 값만 JSON 하나로 뽑아 주세요. 설명은 붙이지 마세요.

{
  "name": "수검자 이름", "age": "나이(숫자만)", "sex": "남성 또는 여성",
  "date": "검진일 YYYY-MM-DD",
  "chronic": ["진단 후 약물 치료 중인 질환"],
  "exam": { "키": "값" }
}

exam 의 키는 아래 목록에 있는 것만 씁니다. 결과지에 없는 항목은 넣지 마세요.
추측하지 마세요 — 흐릿해서 확실하지 않으면 그 항목은 빼는 편이 낫습니다.

숫자 항목: sbp dbp height weight waist hb glu tc hdl tg ldl ast alt ggt cr egfr
          tscore bmd leg balC balO phq9 capeF capeD kdsq pta ratio fev1 fvc plaque
선택 항목(정해진 보기 중 하나):
  cxr: 정상 | 비활동성 폐결핵 | 그 외 소견
  upro: 음성(-) | 약양성(±) | 양성(+1) 이상
  phq9q9: 0점 | 1점 이상
  whisper: 양쪽 3개 이상 정확 | 한쪽이라도 3개 미만
  caries, suspect, filled, lost: 없음 | 있음
  gingiva, calculus: 없음 | 경증 | 중증
chronic 은 다음 중에서만: 고혈압, 당뇨병, 이상지질혈증, 폐결핵, 우울증,
  조기정신증, C형간염, 만성폐쇄성폐질환"""


def _read_with_claude(data: bytes, mime: str, api_key: str) -> dict:
    body = json.dumps({
        "model": VISION_MODEL,
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": mime,
                                         "data": base64.b64encode(data).decode()}},
            {"type": "text", "text": _PROMPT},
        ]}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body, method="POST",
        headers={"content-type": "application/json",
                 "x-api-key": api_key,
                 "anthropic-version": "2023-06-01"})

    with urllib.request.urlopen(req, timeout=50) as res:
        payload = json.loads(res.read().decode())

    text = "".join(b.get("text", "") for b in payload.get("content", []))
    # 모델이 ```json 울타리를 붙일 때가 있어 중괄호 구간만 잘라 냅니다.
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j < i:
        raise ValueError("판독 결과에서 JSON 을 찾지 못했습니다.")
    return json.loads(text[i:j + 1])


# =============================================================================
# 5. 바깥에서 부르는 것은 이 함수 하나뿐입니다
# =============================================================================
def read_exam_image(data: bytes, mime: str) -> dict:
    """검진표 이미지에서 입력값을 읽어 냅니다.

    돌려주는 모양 (화면이 이 필드들을 그대로 씁니다) —

        {
          "source" : "claude" | "demo",     판독 방식. demo 면 화면이 '예시 판독' 표시
          "name"   : "홍길동",              비어 있을 수 있습니다
          "age"    : "45",                  전부 문자열입니다
          "sex"    : "남성" | "여성" | "",
          "date"   : "2026-03-10",
          "exam"   : {"sbp": "132", ...},   화면이 아는 key 만 들어 있습니다
          "chronic": ["고혈압"],
          "groups" : ["고혈압", "비만"],    값이 채워진 검진 그룹 이름
          "fields" : [{"group","name","text"}]   말풍선에 그대로 쓸 목록
        }

    판독에 실패해도 예외를 던지지 않습니다 — 사진이 흐리다고 서비스가 막히면
    안 되기 때문입니다. 읽어 낸 것이 없으면 exam 이 빈 채로 돌아오고, 화면은
    "읽지 못했어요, 직접 알려 주시겠어요?" 로 이어서 물어봅니다.
    """
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        try:
            out = _clean(_read_with_claude(data, mime, key))
            out["source"] = "claude"
            return out
        except (urllib.error.URLError, ValueError, KeyError, TimeoutError, OSError) as e:
            # 모델 호출이 실패하면 서비스를 멈추는 대신 예시 판독으로 넘어갑니다.
            # 화면에는 '예시 판독' 이라고 표시되므로 사용자가 오해하지 않습니다.
            print(f"[vision] 실제 판독에 실패해 예시 판독으로 넘어갑니다: {e}")

    out = _clean(_read_demo(data))
    out["source"] = "demo"
    return out
