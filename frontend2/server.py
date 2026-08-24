"""
server.py — MyHerb 로컬 서버
==============================================================================
'백엔드 연동 규격서' 의 엔드포인트 아홉 개를 그대로 구현한 예시 서버입니다.
화면(static/)까지 같은 주소에서 함께 내려주므로 CORS 설정이 필요 없습니다.

    uv run server.py     →     http://localhost:3000

  GET  /api/bootstrap    화면 열 때 한 번. 성분 이름 추천 목록
  GET  /api/me           지금 로그인되어 있는지
  POST /api/signup       회원가입      POST /api/login   로그인
  POST /api/logout       로그아웃
  GET  /api/draft        저장해 둔 입력값 불러오기
  PUT  /api/draft        입력값 저장 (입력하는 동안 자동으로)
  POST /api/analyze      ★ 핵심. 입력을 보내고 판정 결과를 받습니다
  GET  /api/reports      지난 리포트 목록
  GET  /api/reports/{id} 지난 리포트 하나

------------------------------------------------------------------------------
※ 이 서버는 '확인용' 입니다. 그대로 배포하면 안 됩니다.
    · 로그인이 **무조건 성공**합니다 (아래 [로그인 규칙] 참고)
    · 데이터가 메모리에만 있습니다. 서버를 끄면 전부 사라집니다
    · 비밀번호를 아예 보지 않습니다 (해시는커녕 검사조차 하지 않습니다)
  실제 서비스로 갈 때 확인할 것은 규격서 7장에 정리되어 있습니다.
==============================================================================
"""

import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from analyze import report_info, summary_line, to_report
from schema_bridge import (BLOCKED, FAIL, looks_like_internal_error,
                           to_recommend_form, to_session_user, to_user_id)
from standards import nut_hints
from vision import MAX_IMAGE_BYTES, read_exam_image, sniff_image

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"

COOKIE = "myherb_sid"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7        # 7일

# =============================================================================
# 에이전트 서버 (agent/server.py)
# -----------------------------------------------------------------------------
# 로그인·회원가입·결과보기 세 가지는 이 서버가 직접 계산하지 않고 에이전트에
# 넘깁니다. 나머지(bootstrap·me·draft·reports·exam-image)는 에이전트에 없으므로
# 여기서 계속 처리합니다.
#
# 브라우저가 8000 번을 직접 부르지 않고 이 서버를 거치는 이유:
#   · 에이전트에 CORS 설정이 없어서, 브라우저가 직접 부르면 응답을 읽지
#     못합니다(요청은 가는데 결과를 못 받는 최악의 형태가 됩니다).
#   · 경로(/api/v1/*)와 형식(form-data)이 화면 규격과 달라서, 그 변환을
#     여기 한 곳에 모아 두면 화면 코드를 고치지 않아도 됩니다.
# =============================================================================
API_URL = os.environ.get("API_URL", "http://localhost:8000")

# 결과보기는 LLM·그래프를 타서 오래 걸립니다. 로그인·가입은 그럴 일이 없습니다.
AGENT_TIMEOUT_AUTH = 20.0
AGENT_TIMEOUT_RECOMMEND = 180.0


def _as_number(value, cast):
    """'45' → 45 처럼 숫자로 읽히면 바꿔 주고, 아니면 None.

    화면에서 오는 값은 전부 문자열이고 비어 있을 수 있습니다("58kg" 처럼
    단위가 붙어 오기도 합니다). 에이전트는 int/float 로 선언해 두었으므로
    읽히지 않는 값을 그대로 보내면 422 가 됩니다.
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


async def call_agent(path: str, fields: dict, timeout: float, file=None) -> dict:
    """에이전트를 부르고 data 만 돌려줍니다. 실패는 전부 HTTPException 으로 바꿉니다.

    에이전트의 응답 규약이 이 서버와 두 가지가 다릅니다.
      1. 본문이 {status, message, data} 로 한 겹 싸여 있습니다.
      2. **실패해도 HTTP 200** 입니다. status 를 봐야 실패인 줄 압니다.
    두 가지를 여기서 흡수해서, 위쪽 코드는 평범한 dict 만 다루게 합니다.
    """
    # None·빈 값은 아예 보내지 않습니다. 에이전트 쪽 필드가 전부 Optional 이라
    # 빈 문자열을 보내면 '값이 있다'고 잘못 읽힐 수 있습니다.
    data = {k: str(v) for k, v in fields.items() if v is not None and str(v) != ""}

    # file 은 (파일명, 바이트, mime) 한 벌입니다. 넘어온 경우에만 실어 보냅니다.
    files = {"file": file} if file else None

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(API_URL + path, data=data, files=files)
    except httpx.TimeoutException:
        raise HTTPException(504, "분석 서버가 제때 응답하지 않았습니다. 잠시 후 다시 시도해 주세요.")
    except httpx.RequestError:
        raise HTTPException(502, "분석 서버에 연결하지 못했습니다. 서버가 켜져 있는지 확인해 주세요.")

    if res.status_code == 422:
        # 필수 항목이 빠졌을 때. 화면이 보낸 값이 규격과 어긋난 경우입니다.
        raise HTTPException(400, "입력값을 다시 확인해 주세요.")
    if res.status_code >= 500:
        raise HTTPException(502, "분석 서버에 문제가 생겼습니다.")

    try:
        body = res.json()
    except ValueError:
        raise HTTPException(502, "분석 서버가 알 수 없는 형식으로 응답했습니다.")

    # 'blocked' 는 에이전트의 안전 가드레일(agent/guardrails)이 리포트 제공을
    # 막았다는 뜻입니다. 실패와 달리 **다시 시도해도 같은 결과**이므로,
    # 에이전트가 준 안내 문구를 그대로 사용자에게 전달합니다.
    # 이 응답에는 data 가 없어서, 그냥 통과시키면 빈 리포트가 되어 엉뚱한
    # 서버 오류처럼 보입니다.
    if body.get("status") == BLOCKED:
        raise HTTPException(400, (body.get("message") or "").strip()
                            or "안전 검증에서 문제가 발견되어 리포트를 제공할 수 없습니다. "
                               "전문가와 상담하시기를 권장드립니다.")

    if body.get("status") == FAIL:
        msg = (body.get("message") or "").strip()
        # 에이전트가 파이썬 예외를 그대로 문자열로 내보내는 경우가 있습니다
        # (예: KeyError 는 "'pwd'" 로 옵니다). 그대로 보여 주면 사용자가
        # 무슨 말인지 알 수 없으므로 일반 문구로 바꿉니다.
        if looks_like_internal_error(msg):
            msg = "요청을 처리하지 못했습니다."
        # ★ 401 을 쓰면 안 됩니다. 이 서비스에서 401 은 '세션이 끊겼다' 는
        #   뜻이라, 화면이 재로그인 창을 다시 띄우는 무한 반복이 됩니다.
        raise HTTPException(400, msg)

    return body.get("data") or {}

# 성분 기준값과 상호작용 규칙이 아직 검증되지 않았다는 뜻입니다.
# True 인 동안 화면 맨 위에 '예시 기준값으로 계산 중입니다' 경고 띠가 뜹니다.
# 검증된 기준(KDRI 등)으로 교체한 뒤에 False 로 바꾸세요.
UNVERIFIED = True

app = FastAPI(title="MyHerb 로컬 서버", docs_url="/api/docs", redoc_url=None)


# =============================================================================
# 저장소 — 전부 메모리입니다. 서버를 끄면 사라집니다.
# -----------------------------------------------------------------------------
# 실제 서비스에서는 이 네 개가 전부 DB 테이블이 됩니다. 건강검진 결과와 복약
# 정보는 민감정보이므로, 보관 기간·파기 절차·접근 통제를 함께 정해야 합니다.
# =============================================================================
SESSIONS: dict[str, str] = {}            # sid            → email
USERS: dict[str, dict] = {}              # email(정규화)  → {name, email}
DRAFTS: dict[str, dict] = {}             # email          → Input
REPORTS: dict[str, list] = {}            # email          → [{id, createdAt, report}] 최신순


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def norm_email(email) -> str:
    return str(email or "").strip().lower()


# =============================================================================
# 오류 응답 — 규격서 §2.4 의 모양({"message": ...})으로 맞춥니다
# -----------------------------------------------------------------------------
# FastAPI 의 기본 오류 본문은 {"detail": ...} 라서 그대로 두면 화면이 서버
# 메시지를 읽지 못합니다. 여기서 한 번에 바꿔 줍니다.
# =============================================================================
@app.exception_handler(StarletteHTTPException)
async def to_message_body(request: Request, exc: StarletteHTTPException):
    return JSONResponse({"message": exc.detail}, status_code=exc.status_code)


# =============================================================================
# 세션
# -----------------------------------------------------------------------------
# 쿠키 세션입니다. 토큰을 헤더에 싣지 않습니다 — 화면은 모든 요청을
# credentials:'include' 로 보내므로 쿠키가 자동으로 함께 갑니다.
# =============================================================================
def start_session(response: Response, user: dict) -> None:
    sid = secrets.token_urlsafe(32)
    SESSIONS[sid] = user["email"]
    response.set_cookie(
        COOKIE, sid,
        max_age=COOKIE_MAX_AGE,
        httponly=True,          # 자바스크립트가 읽지 못하게
        samesite="lax",
        path="/",
        # HTTPS 로 배포할 때는 secure=True 를 켜세요.
        # 지금은 http://localhost 라서 켜면 쿠키가 아예 저장되지 않습니다.
        secure=False,
    )


def current_user(request: Request):
    """지금 로그인한 사용자. 아니면 None."""
    sid = request.cookies.get(COOKIE)
    if not sid:
        return None
    email = SESSIONS.get(sid)
    if not email:
        return None
    return USERS.get(email)


def require_user(request: Request) -> dict:
    """로그인이 필요한 요청에서 씁니다.

    ★ 401 은 이 서비스 전체에서 '세션이 없거나 끊겼다' 는 뜻으로만 씁니다.
      로그인 요청이 거절된 경우에 401 을 쓰면, 화면이 그것을 '세션 만료' 로
      읽고 재로그인 창을 다시 띄웁니다. 사용자는 같은 창이 계속 뜨는 것만
      보게 됩니다. (규격서 §2.3)
    """
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return user


# =============================================================================
# Input 정리 — 화면이 보낸 값을 계산이 기대하는 모양으로 맞춥니다
# -----------------------------------------------------------------------------
# 화면에서 온 값은 전부 문자열이고, 비어 있을 수 있습니다("45" 이지 45 가
# 아닙니다). 여기서 없는 키를 채워 두면 이후 계산이 매번 존재 여부를 확인하지
# 않아도 됩니다.
# =============================================================================
def normalize_input(raw) -> dict:
    raw = raw if isinstance(raw, dict) else {}

    products = []
    for p in (raw.get("products") or []):
        if not isinstance(p, dict):
            continue
        items = []
        for it in (p.get("items") or []):
            if not isinstance(it, dict):
                continue
            items.append({
                "name": str(it.get("name") or "").strip(),
                "amount": it.get("amount", ""),
                "unit": it.get("unit") or "mg",
            })
        products.append({"name": str(p.get("name") or "").strip(), "items": items})

    meds = []
    for m in (raw.get("meds") or []):
        if not isinstance(m, dict):
            continue
        meds.append({"name": str(m.get("name") or "").strip(),
                     "desc": str(m.get("desc") or "").strip()})

    exam = raw.get("exam")
    exam = {k: v for k, v in exam.items()} if isinstance(exam, dict) else {}

    return {
        "name": str(raw.get("name") or ""),
        "age": str(raw.get("age") or ""),
        "sex": str(raw.get("sex") or ""),
        # 검진일은 형식이 정해져 있지 않습니다. 대화형 입력에서는
        # "작년 11월 중순쯤" 같은 문장이 그대로 들어옵니다. 표시용이며
        # 계산에 쓰지 않으므로 손대지 않고 그대로 둡니다.
        "date": str(raw.get("date") or ""),
        "countMeal": bool(raw.get("countMeal")),
        "exam": exam,
        "chronic": [str(c) for c in (raw.get("chronic") or [])],
        "products": products,
        "meds": meds,
    }


# =============================================================================
# 1. 화면 열 때
# =============================================================================
@app.get("/api/bootstrap")
async def bootstrap():
    """로그인 전에도 부를 수 있어야 합니다. 실패해도 화면은 그냥 열립니다."""
    return {"nutHints": nut_hints(), "unverified": UNVERIFIED}


# =============================================================================
# 2. 인증
# -----------------------------------------------------------------------------
# ★★★ [로그인 규칙] 이 서버는 로그인·회원가입이 무조건 성공합니다 ★★★
#
#   숙제 요구사항: "로그인 시 함수 호출하고 결과를 무조건 성공한 걸로 받아서
#                  해당 사용자로 로그인 하도록 할 것"
#
#   그래서 비밀번호를 **검사하지 않습니다**. 어떤 이메일·비밀번호를 넣어도
#   그 이메일의 사용자로 세션이 만들어집니다. 이메일마다 데이터가 따로
#   쌓이므로, 다른 이메일로 로그인하면 다른 사람의 화면이 됩니다.
#
#   실제 서비스로 바꿀 때는 아래 _login_always_ok() 안쪽만 고치면 됩니다.
#   화면 코드는 한 줄도 건드릴 필요가 없습니다 — 실패를 400 으로 내려보내면
#   화면이 그 문구를 사용자에게 그대로 보여 줍니다(규격서 §2.3).
# =============================================================================
def _login_always_ok(name: str, email: str) -> dict:
    """이메일 하나로 사용자를 만들어(또는 찾아) 돌려줍니다. 절대 실패하지 않습니다."""
    key = norm_email(email)
    if not key:
        # 이메일까지 비워서 보낸 경우에도 막지 않습니다. 손님 계정으로 받습니다.
        key = "guest@myherb.local"

    existing = USERS.get(key)
    display = (name or "").strip()
    if not display:
        # 이름을 안 적었으면 이메일 앞부분을 이름으로 씁니다.
        display = existing["name"] if existing else key.split("@")[0]

    user = {"name": display, "email": key}
    USERS[key] = user
    return user


def _adopt_agent_user(response: Response, data: dict, fallback_email: str,
                      fallback_name: str = "") -> dict:
    """에이전트가 확인해 준 사용자로 이 서버의 세션을 엽니다.

    세션은 계속 이 서버가 쥡니다 — 에이전트에는 로그인 개념이 없어서
    (쿠키도 토큰도 내려주지 않습니다), 여기서 세션을 만들지 않으면
    임시저장(draft)과 지난 리포트(reports)가 전부 동작하지 않습니다.
    """
    su = to_session_user(data, fallback_email, fallback_name)
    key = su["id"] or "guest@myherb.local"
    name = su["name"] or (USERS[key]["name"] if key in USERS else key.split("@")[0])

    # 화면은 {name, email} 을 기대합니다. id 는 같은 값의 다른 이름입니다.
    user = {"name": name, "email": key}
    USERS[key] = user
    start_session(response, user)
    return user


@app.post("/api/login")
async def login(request: Request, response: Response):
    """판정은 에이전트가 합니다. 이 서버는 세션만 엽니다."""
    body = await request.json() if await request.body() else {}
    body = body or {}
    email = body.get("email") or ""

    data = await call_agent(
        "/api/v1/login",
        {"id": email, "pwd": body.get("password") or ""},
        AGENT_TIMEOUT_AUTH,
    )
    return _adopt_agent_user(response, data, email)


@app.post("/api/signup")
async def signup(request: Request, response: Response):
    body = await request.json() if await request.body() else {}
    body = body or {}
    email = body.get("email") or ""
    name = body.get("name") or ""

    data = await call_agent(
        "/api/v1/signup",
        {"id": email, "pwd": body.get("password") or "", "name": name},
        AGENT_TIMEOUT_AUTH,
    )
    return _adopt_agent_user(response, data, email, name)


@app.post("/api/logout")
async def logout(request: Request, response: Response):
    sid = request.cookies.get(COOKIE)
    if sid:
        SESSIONS.pop(sid, None)
    response.delete_cookie(COOKIE, path="/")
    return {}


@app.get("/api/me")
async def me(request: Request):
    """화면은 열릴 때마다 이걸 먼저 불러 로그인 상태를 확인합니다."""
    return require_user(request)


# =============================================================================
# 3. 입력값 임시 저장 (draft)
# =============================================================================
@app.get("/api/draft")
async def get_draft(request: Request):
    """저장한 적이 없으면 null. null 은 오류가 아닙니다."""
    user = require_user(request)
    return DRAFTS.get(user["email"])


@app.put("/api/draft")
async def put_draft(request: Request):
    user = require_user(request)
    body = await request.json() if await request.body() else {}
    DRAFTS[user["email"]] = normalize_input(body)
    return {"savedAt": now_iso()}


# =============================================================================
# 4. ★ 판정
# =============================================================================
@app.post("/api/analyze")
async def analyze(request: Request):
    """입력을 받아 리포트를 만들고, 이력에 자동으로 남깁니다.

    화면은 따로 '저장' 요청을 보내지 않습니다. 여기서 남기지 않으면
    목록 화면이 계속 비어 있게 됩니다.
    """
    user = require_user(request)

    # 화면은 두 가지 모양으로 보냅니다.
    #   · 검진표 사진이 없으면  application/json  (예전 그대로)
    #   · 사진이 있으면        multipart/form-data — input(JSON 문자열) + file
    # 사진은 여기서 **저장하지 않습니다.** 받은 즉시 에이전트로 흘려보내고
    # 요청이 끝나면 사라집니다(민감정보라 서버에 남기지 않습니다).
    upload = None
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("multipart/form-data"):
        form = await request.form()
        raw = form.get("input") or "{}"
        try:
            body = json.loads(raw)
        except ValueError:
            raise HTTPException(400, "입력값을 읽지 못했습니다.")

        up = form.get("file")
        if up is not None and hasattr(up, "read"):
            blob = await up.read()
            if len(blob) > MAX_IMAGE_BYTES:
                raise HTTPException(400, f"이미지가 너무 큽니다. {MAX_IMAGE_BYTES // (1024 * 1024)}MB 이하로 올려 주세요.")
            mime = sniff_image(blob)
            if not mime:
                raise HTTPException(400, "이미지 파일만 올릴 수 있습니다. (PNG · JPG · GIF · WEBP · HEIC)")
            upload = (up.filename or "exam", blob, mime)
    else:
        body = await request.json() if await request.body() else {}

    state = normalize_input(body)

    # 화면 규격 → 에이전트 규격 변환은 schema_bridge 한 곳에서만 합니다.
    data = await call_agent(
        "/api/v1/recommend",
        to_recommend_form(state),
        AGENT_TIMEOUT_RECOMMEND,
        file=upload,
    )

    html = (data.get("html") or "").strip()
    if not html:
        raise HTTPException(502, "분석 서버가 리포트를 만들지 못했습니다.")

    # 화면에 보이는 내용은 위의 html 이 전부입니다. 그런데 '지난 리포트'
    # 목록은 요약 한 줄·배지·최고 심각도를 리포트 구조에서 뽑아 쓰므로
    # (list_reports 참고), html 만 저장하면 목록이 빈칸투성이가 됩니다.
    # 그래서 목록에 쓸 뼈대는 여기서 그대로 만들어 두고, 화면이 실제로
    # 그릴 html 만 얹습니다.
    report = to_report(state)
    report["html"] = html
    if data.get("disclaimer"):
        report["agentDisclaimer"] = data["disclaimer"]
    report["partialFailure"] = bool(data.get("partial_failure"))

    entry = {
        "id": "r" + secrets.token_hex(8),
        "createdAt": now_iso(),
        "report": report,
    }
    REPORTS.setdefault(user["email"], []).insert(0, entry)   # 최신순
    return report


# =============================================================================
# 5. 지난 리포트
# =============================================================================
@app.get("/api/reports")
async def list_reports(request: Request):
    """목록은 가볍게 — 성분 카드 전체를 내려 주지 않습니다.

    다만 '무엇을 입력해서 나온 리포트인지'(info)는 함께 보냅니다. 날짜와
    배지만으로는 같은 날 여러 번 돌린 리포트를 구분할 수 없기 때문입니다.
    """
    user = require_user(request)
    items = REPORTS.get(user["email"], [])
    return {"reports": [{
        "id": e["id"],
        "createdAt": e["createdAt"],
        "summaryLine": summary_line(e["report"]),
        "worst": e["report"]["worst"],
        "badges": e["report"]["badges"],
        "info": report_info(e["report"]),
    } for e in items]}


@app.get("/api/reports/{report_id}")
async def get_report(report_id: str, request: Request):
    """analyze 와 똑같은 Report 를 통째로 돌려줍니다."""
    user = require_user(request)
    for e in REPORTS.get(user["email"], []):
        if e["id"] == report_id:
            return e["report"]
    raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")


@app.delete("/api/reports/{report_id}")
async def delete_report(report_id: str, request: Request):
    """리포트 하나를 지웁니다.

    남의 리포트 id 를 넣어도 지워지지 않습니다 — 로그인한 사용자의 목록
    안에서만 찾기 때문에, 남의 것은 '없는 id' 와 똑같이 404 가 됩니다.
    (있는데 권한이 없다고 알려 주면, 그 id 가 존재한다는 사실이 새어 나갑니다.)
    """
    user = require_user(request)
    items = REPORTS.get(user["email"], [])
    for i, e in enumerate(items):
        if e["id"] == report_id:
            items.pop(i)
            return {"deleted": report_id, "remaining": len(items)}
    raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다.")


# =============================================================================
# 5-B. 검진표 이미지 판독
# -----------------------------------------------------------------------------
# 화면의 ＋ 버튼이 고른 사진이 여기로 옵니다. multipart 대신 **본문에 바이트를
# 그대로** 받습니다 — 파일 하나뿐이라 경계 파싱이 필요 없고, 의존성
# (python-multipart)도 늘지 않기 때문입니다.
# =============================================================================
@app.post("/api/exam-image")
async def exam_image(request: Request):
    """검진표 사진에서 읽어 낸 입력값을 돌려줍니다.

    ※ 이미지만 받습니다. 확장자나 브라우저가 보낸 Content-Type 은 믿지 않고
      파일 앞머리의 매직 넘버로 직접 확인합니다 — 둘 다 사용자가 마음대로
      적어 보낼 수 있기 때문입니다.
    """
    require_user(request)

    # 다 읽기 전에 먼저 걸러 냅니다. 큰 파일을 통째로 메모리에 올리고 나서
    # 거절하면, 거절하는 요청만으로도 서버가 흔들립니다.
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400,
                            detail=f"이미지가 너무 큽니다. {MAX_IMAGE_BYTES // (1024 * 1024)}MB 이하로 올려 주세요.")

    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="이미지가 비어 있습니다.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400,
                            detail=f"이미지가 너무 큽니다. {MAX_IMAGE_BYTES // (1024 * 1024)}MB 이하로 올려 주세요.")

    mime = sniff_image(data)
    if not mime:
        raise HTTPException(status_code=400,
                            detail="이미지 파일만 올릴 수 있습니다. (PNG · JPG · GIF · WEBP · HEIC)")

    return read_exam_image(data, mime)


# =============================================================================
# 6. 화면 — API 와 같은 주소에서 내려줍니다
# -----------------------------------------------------------------------------
# 같은 주소에서 함께 돌기 때문에 CORS 설정이 아예 필요 없고, 화면의
# API_BASE 도 '' 로 비워 둘 수 있습니다.
#
# ※ mount 는 반드시 맨 마지막이어야 합니다. 위에서 정의한 /api/* 경로보다
#   먼저 걸리면 API 요청이 정적 파일 찾기로 새어 나갑니다.
# =============================================================================
@app.get("/")
async def index():
    return FileResponse(
        STATIC / "Live.html",
        # 개발 중에는 화면을 고치고 새로고침하면 바로 보여야 합니다.
        headers={"Cache-Control": "no-store"},
    )


if not STATIC.is_dir():
    raise SystemExit(
        f"화면 파일이 없습니다: {STATIC}\n"
        f"  src/ 에서 'node build-live.js' 를 실행해 static/ 을 만들어 주세요."
    )

app.mount("/", StaticFiles(directory=STATIC), name="static")


def main():
    import uvicorn
    port = int(os.environ.get("PORT", "3000"))
    print(f"\n  MyHerb  →  http://localhost:{port}\n"
          f"  API 문서   →  http://localhost:{port}/api/docs\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
