# -*- coding: utf-8 -*-
"""REST API 검증 — 실제 HTTP 로 /api/v1/signup · /api/v1/login 을 호출한다.

    python test_api.py            (에이전트가 :8000 에 떠 있어야 합니다)

브라우저와 같은 방식(multipart/form-data, UTF-8)으로 보냅니다.
테스트 계정은 'qa_test_' 로 시작하며 끝나면 지웁니다.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = "http://localhost:8000"
BOUNDARY = "----qaAuthBoundary42"
PREFIX = "qa_test_"

passed = failed = 0


def post(path, fields):
    parts = []
    for k, v in fields.items():
        parts += [("--" + BOUNDARY).encode(),
                  (f'Content-Disposition: form-data; name="{k}"').encode(),
                  b"",
                  str(v).encode("utf-8")]          # 브라우저와 동일하게 UTF-8
    parts.append(("--" + BOUNDARY + "--").encode())
    body = b"\r\n".join(parts) + b"\r\n"

    req = urllib.request.Request(
        BASE + path, data=body, method="POST",
        headers={"Content-Type": "multipart/form-data; boundary=" + BOUNDARY})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8", "replace") or "{}")


def check(name, got, want):
    global passed, failed
    ok = got == want
    passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)
    print(f"  {'[ OK ]' if ok else '[FAIL]'} {name}")
    if not ok:
        print(f"         기대={want!r}  실제={got!r}")


uid = f"{PREFIX}{int(time.time())}@example.com"
PWD = "test1234"

print("\n=== 회원가입 API ===")
code, b = post("/api/v1/signup", {"id": uid, "pwd": PWD, "name": "홍길동"})
check("HTTP 200", code, 200)
check("status success", b.get("status"), "success")
check("아이디 반환", (b.get("data") or {}).get("user", {}).get("id"), uid)
check("이름 반환(한글)", (b.get("data") or {}).get("user", {}).get("name"), "홍길동")
check("비밀번호가 응답에 없음", "pwd" in json.dumps(b), False)

code, b = post("/api/v1/signup", {"id": uid, "pwd": PWD, "name": "중복"})
check("중복 가입 거부", b.get("status"), "fail")
check("중복 안내 문구", b.get("message"), "이미 존재하는 아이디입니다.")

# 빈 값은 FastAPI 가 '필드 누락' 으로 보고 우리 코드 이전에 422 로 막습니다.
# 거부된다는 결과는 같지만 응답 형태가 {status,message,data} 봉투가 아니라
# {detail:[...]} 입니다. 클라이언트는 두 형태를 모두 처리해야 합니다.
code, b = post("/api/v1/signup", {"id": "", "pwd": PWD, "name": "홍길동"})
check("빈 아이디 거부(422 또는 fail)",
      code == 422 or b.get("status") == "fail", True)

code, b = post("/api/v1/signup", {"id": PREFIX + "x@e.com", "pwd": "1", "name": "홍"})
check("짧은 비밀번호 거부", b.get("status"), "fail")

print("\n=== 로그인 API ===")
code, b = post("/api/v1/login", {"id": uid, "pwd": PWD})
check("HTTP 200", code, 200)
check("status success", b.get("status"), "success")
check("이름 반환", (b.get("data") or {}).get("user", {}).get("name"), "홍길동")

code, b = post("/api/v1/login", {"id": uid, "pwd": "wrong"})
check("틀린 비밀번호 거부", b.get("status"), "fail")
check("실패 문구 통일", b.get("message"), "아이디 또는 비밀번호가 올바르지 않습니다.")

code, b = post("/api/v1/login", {"id": PREFIX + "nobody@e.com", "pwd": PWD})
check("없는 아이디 거부", b.get("status"), "fail")
check("없는 아이디도 같은 문구", b.get("message"), "아이디 또는 비밀번호가 올바르지 않습니다.")

code, b = post("/api/v1/login", {"id": uid.upper(), "pwd": PWD})
check("대소문자 무관 로그인", b.get("status"), "success")

print("\n=== 정리 ===")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))
from services import db_helper  # noqa: E402
with db_helper.get_db_connection() as conn, conn.cursor() as cur:
    cur.execute("DELETE FROM users WHERE id LIKE %s", (PREFIX + "%",))
    print(f"  테스트 계정 {cur.rowcount}건 삭제")
    cur.execute("SELECT COUNT(*) AS n FROM users")
    print(f"  users 최종: {cur.fetchone()['n']}행")

print(f"\n=== 결과: {passed}/{passed + failed} 통과 ===")
sys.exit(1 if failed else 0)
