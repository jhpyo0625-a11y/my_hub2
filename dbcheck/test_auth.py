# -*- coding: utf-8 -*-
"""회원가입 · 로그인 통합 검증 (지시 2, 3).

    uv run --directory ../agent python ../dbcheck/test_auth.py
    또는  cd dbcheck && python test_auth.py   (agent venv 가 필요합니다)

실제 Neon DB 에 씁니다. 계정은 전부 'qa_test_' 로 시작하게 만들고,
끝나면 지웁니다. 중간에 실패해도 finally 에서 정리합니다.
"""
import sys
import time
from pathlib import Path

AGENT = Path(__file__).resolve().parent.parent / "agent"
sys.path.insert(0, str(AGENT))

from services import db_helper  # noqa: E402

PREFIX = "qa_test_"
made = []

passed = failed = 0


def check(name, got, want):
    global passed, failed
    ok = got == want
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"  {'[ OK ]' if ok else '[FAIL]'} {name}")
    if not ok:
        print(f"         기대={want!r}  실제={got!r}")


def check_true(name, cond, note=""):
    check(name + (f" ({note})" if note else ""), bool(cond), True)


def main():
    uid = f"{PREFIX}{int(time.time())}@example.com"
    pwd = "test1234"

    print("\n=== 순수 로직 (DB 없이) ===")
    h = db_helper.hash_password(pwd)
    check_true("해시가 평문과 다름", h != pwd)
    check_true("bcrypt 형식", h.startswith("$2"))
    check_true("길이가 255 이하", len(h) <= 255, f"{len(h)}자")
    check("올바른 비밀번호 검증", db_helper.verify_password(pwd, h), True)
    check("틀린 비밀번호 거부", db_helper.verify_password("wrong", h), False)
    check("깨진 해시 거부", db_helper.verify_password(pwd, "not-a-hash"), False)
    check("같은 비밀번호도 해시가 다름(salt)",
          db_helper.hash_password(pwd) == db_helper.hash_password(pwd), False)

    check("아이디 정규화(대소문자·공백)",
          db_helper.normalize_user_id("  ABC@Example.COM "), "abc@example.com")

    check("빈 아이디 거부", db_helper.validate_signup("", pwd, "홍길동") is not None, True)
    check("짧은 비밀번호 거부", db_helper.validate_signup(uid, "1", "홍길동") is not None, True)
    check("빈 이름 거부", db_helper.validate_signup(uid, pwd, " ") is not None, True)
    check("51자 아이디 거부",
          db_helper.validate_signup("a" * 51, pwd, "홍길동") is not None, True)
    check("정상 입력 통과", db_helper.validate_signup(uid, pwd, "홍길동"), None)

    print("\n=== DB 연동 ===")
    user = db_helper.create_user(uid, pwd, "테스트계정")
    made.append(uid)
    check("가입 후 아이디", user["id"], uid)
    check("가입 후 이름", user["name"], "테스트계정")

    row = db_helper.find_user(uid)
    check_true("DB 에서 조회됨", row is not None)
    check_true("평문이 저장되지 않음", row["pwd_hash"] != pwd)
    check_true("해시가 저장됨", row["pwd_hash"].startswith("$2"))

    check("대소문자 달라도 같은 계정",
          db_helper.find_user(uid.upper())["id"], uid)

    try:
        db_helper.create_user(uid, pwd, "중복시도")
        check("중복 가입 차단", "차단 안 됨", "차단")
    except db_helper.DuplicateUser:
        check_true("중복 가입 차단", True)

    print("\n=== 로그인 ===")
    ok = db_helper.authenticate(uid, pwd)
    check_true("올바른 계정 로그인 성공", ok is not None)
    check("로그인 결과 이름", ok["name"], "테스트계정")
    check("해시가 밖으로 새지 않음", "pwd_hash" in (ok or {}), False)

    check("틀린 비밀번호 거부", db_helper.authenticate(uid, "wrong"), None)
    check("없는 아이디 거부", db_helper.authenticate(PREFIX + "nobody", pwd), None)
    check("빈 비밀번호 거부", db_helper.authenticate(uid, ""), None)

    # 응답 시간이 비슷해야 '그 아이디가 있는지' 를 시간으로 알아낼 수 없습니다.
    t0 = time.time(); db_helper.authenticate(uid, "wrong"); t_exist = time.time() - t0
    t0 = time.time(); db_helper.authenticate(PREFIX + "nobody", "wrong"); t_none = time.time() - t0
    ratio = max(t_exist, t_none) / max(min(t_exist, t_none), 1e-6)
    check_true("존재/부재 응답시간이 비슷함", ratio < 3,
               f"{t_exist*1000:.0f}ms vs {t_none*1000:.0f}ms")


def cleanup():
    print("\n=== 정리 ===")
    for uid in made:
        n = db_helper.delete_user(uid)
        print(f"  삭제 {uid} -> {n}행")
    # 혹시 남아 있는 테스트 계정도 함께 정리합니다.
    with db_helper.get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM users WHERE id LIKE %s", (PREFIX + "%",))
        if cur.rowcount:
            print(f"  잔여 테스트 계정 {cur.rowcount}건 삭제")
        cur.execute("SELECT COUNT(*) AS n FROM users")
        print(f"  users 테이블 최종: {cur.fetchone()['n']}행")


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup()
    print(f"\n=== 결과: {passed}/{passed + failed} 통과 ===")
    sys.exit(1 if failed else 0)
