# -*- coding: utf-8 -*-
"""DB 연동 점검 — 무엇이 붙어 있고 무엇이 안 붙어 있는지 한 번에 확인한다.

    uv run python check_db.py

왜 필요한가 ---------------------------------------------------------------
executor.py 는 `MCP → DB 직접조회 → 결정적 stub` 3단으로 떨어지면서 예외를
전부 삼킵니다. 그래서 DB가 완전히 끊겨 있어도 API 는 status:"success" 를
돌려줍니다. 즉 **API 를 불러 보는 것으로는 연동 여부를 알 수 없습니다.**
이 스크립트는 각 계층을 직접 찔러서 실제 상태를 판정합니다.
"""
import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent          # dbcheck/
AGENT = BASE.parent / "agent"                   # config 와 db_helper 가 있는 곳
sys.path.insert(0, str(AGENT))
OUT = BASE / "out"

from config import DATABASE_URL, MCP_SERVER_URL  # noqa: E402

# 코드가 실제로 쓰는 테이블 (db_helper.py · mcp/main.py 에서 확인)
EXPECTED_TABLES = {
    "users":                      "회원 (signup·login)",
    "kdri_standards":             "영양 기준값 (RI·UL)",
    "nutrient_codes":             "영양소 코드·단위",
    "product_ingredients_master": "제품 성분",
    "prescription_histories":     "리포트 이력",
    "user_health_presets":        "건강 프리셋",
}

rows = []      # (구분, 항목, 상태, 상세)
OK, NG, WARN = "정상", "실패", "주의"


def add(group, item, status, detail=""):
    rows.append((group, item, status, detail))
    mark = {"정상": "[ OK ]", "실패": "[FAIL]", "주의": "[WARN]"}[status]
    print(f"  {mark} {item:34s} {detail}")


def main():
    print("\n=== 1. 접속 ===")
    if not DATABASE_URL:
        add("접속", "DATABASE_URL", NG, ".env 에 없음")
        print("\nDATABASE_URL 이 없어 이후 점검을 건너뜁니다.")
        return finish()
    add("접속", "DATABASE_URL", OK, "설정됨")

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as e:
        add("접속", "psycopg 설치", NG, str(e))
        return finish()
    add("접속", "psycopg 설치", OK)

    t0 = time.time()
    try:
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=15)
    except Exception as e:
        add("접속", "DB 연결", NG, f"{type(e).__name__}: {str(e)[:90]}")
        return finish()
    ms = int((time.time() - t0) * 1000)
    add("접속", "DB 연결", OK, f"{ms}ms")

    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database() AS db, version() AS v")
            r = cur.fetchone()
            add("접속", "데이터베이스", OK, r["db"])

            # ---- 2. 테이블 ------------------------------------------------
            print("\n=== 2. 테이블 존재 ===")
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                 WHERE table_schema = 'public'
            """)
            actual = {r["table_name"] for r in cur.fetchall()}
            for name, desc in EXPECTED_TABLES.items():
                if name in actual:
                    add("테이블", name, OK, desc)
                else:
                    add("테이블", name, NG, f"{desc} — 없음")

            extra = sorted(actual - set(EXPECTED_TABLES))
            if extra:
                add("테이블", "(코드가 안 쓰는 테이블)", WARN, ", ".join(extra)[:70])

            # ---- 3. 행 수 --------------------------------------------------
            print("\n=== 3. 데이터 (행 0 이면 조용히 빈 결과가 나옵니다) ===")
            for name in EXPECTED_TABLES:
                if name not in actual:
                    continue
                try:
                    cur.execute(f'SELECT COUNT(*) AS n FROM "{name}"')
                    n = cur.fetchone()["n"]
                    add("데이터", name, OK if n else WARN, f"{n:,} 행")
                except Exception as e:
                    add("데이터", name, NG, str(e)[:70])

            # ---- 4. users 스키마 -------------------------------------------
            print("\n=== 4. users 컬럼 ===")
            if "users" in actual:
                cur.execute("""
                    SELECT column_name, data_type, character_maximum_length AS len,
                           is_nullable
                      FROM information_schema.columns
                     WHERE table_schema='public' AND table_name='users'
                     ORDER BY ordinal_position
                """)
                cols = cur.fetchall()
                got = {c["column_name"]: c for c in cols}
                for want in ("id", "pwd_hash", "name", "created_at", "updated_at"):
                    if want in got:
                        c = got[want]
                        ln = f"({c['len']})" if c["len"] else ""
                        add("users", want, OK, f"{c['data_type']}{ln}")
                    else:
                        add("users", want, NG, "컬럼 없음")

                # 아이디 길이 불일치 — 리포트 이력과 연결할 때 문제가 됩니다.
                uid = got.get("id", {}).get("len")
                cur.execute("""
                    SELECT character_maximum_length AS len
                      FROM information_schema.columns
                     WHERE table_schema='public'
                       AND table_name='prescription_histories'
                       AND column_name='user_id'
                """)
                ph = cur.fetchone()
                if uid and ph and ph["len"] and uid != ph["len"]:
                    add("users", "id 길이 정합성", WARN,
                        f"users.id({uid}) ≠ prescription_histories.user_id({ph['len']})")

            # ---- 5. db_helper 쿼리 -----------------------------------------
            print("\n=== 5. db_helper 실제 쿼리 ===")
    try:
        from services import db_helper
        r = db_helper.db_calculate_ri(45, "female", ["vitamin_d", "calcium"])
        n = len(r.get("custom_ri") or {})
        add("쿼리", "db_calculate_ri", OK if n else WARN, f"{n}개 영양소 반환")
    except Exception as e:
        add("쿼리", "db_calculate_ri", NG, f"{type(e).__name__}: {str(e)[:70]}")

    try:
        r = db_helper.db_search_products(["vitamin_d"], limit=3)
        n = len(r.get("products") or [])
        add("쿼리", "db_search_products", OK if n else WARN, f"{n}개 제품 반환")
    except Exception as e:
        add("쿼리", "db_search_products", NG, f"{type(e).__name__}: {str(e)[:70]}")

    try:
        r = db_helper.db_validate_ul({"vitamin_d": 5000}, {}, {}, 45, "female")
        add("쿼리", "db_validate_ul", OK,
            f"안전={r.get('is_safe')} 위반={len(r.get('ul_violations') or [])}")
    except Exception as e:
        add("쿼리", "db_validate_ul", NG, f"{type(e).__name__}: {str(e)[:70]}")

    # ---- 6. MCP --------------------------------------------------------
    print("\n=== 6. MCP 서버 ===")
    # MCP 는 '/' 가 아니라 '/mcp/' 로 서비스합니다. 그래서 '/' 가 404 를
    # 돌려주는 것은 **서버가 살아 있다는 뜻**입니다. 연결 자체가 안 되는
    # 경우(URLError)만 미기동으로 봅니다.
    import urllib.error
    import urllib.request
    try:
        urllib.request.urlopen(MCP_SERVER_URL, timeout=5)
        add("MCP", "기동 여부", OK, MCP_SERVER_URL)
    except urllib.error.HTTPError as e:
        add("MCP", "기동 여부", OK, f"{MCP_SERVER_URL} 응답함 (HTTP {e.code})")
    except Exception as e:
        add("MCP", "기동 여부", NG,
            f"{MCP_SERVER_URL} 연결 안 됨 ({type(e).__name__}) — DB 직접조회로 대체됨")

    finish()


def finish():
    print("\n=== 요약 ===")
    n_ok = sum(1 for r in rows if r[2] == OK)
    n_ng = sum(1 for r in rows if r[2] == NG)
    n_wa = sum(1 for r in rows if r[2] == WARN)
    print(f"  정상 {n_ok} · 주의 {n_wa} · 실패 {n_ng}")

    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "result.json"
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump([{"group": g, "item": i, "status": s, "detail": d}
                   for g, i, s, d in rows], f, ensure_ascii=False, indent=2)
    print(f"  -> {out}")

    csv = OUT / "result.csv"
    with open(csv, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write("구분,항목,상태,상세\n")
        for g, i, s, d in rows:
            d2 = d.replace('"', "'")
            f.write(f'"{g}","{i}","{s}","{d2}"\n')
    print(f"  -> {csv}")


if __name__ == "__main__":
    main()
