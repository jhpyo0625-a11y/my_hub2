"""Neon PostgreSQL 직접 조회. MCP 서버 미구동 시 Executor의 실연동 fallback.

전부 동기(psycopg) 함수. 호출 측(async Executor)은 asyncio.to_thread로 감싼다.
ponytail: 커넥션 풀 없음(요청당 소수 호출). 처리량 늘면 psycopg_pool로 승격.
"""
import psycopg
from psycopg.rows import dict_row
from typing import Any, Dict, List

from config import DATABASE_URL


def get_db_connection():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL이 .env에 설정되어 있지 않습니다.")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def _gender_code(gender: str) -> str:
    return "M" if str(gender).lower() in ("male", "m", "남성", "남자") else "F"


def _fetch_units(cur, codes: List[str]) -> Dict[str, str]:
    cur.execute(
        "SELECT nutrient_code, kdri_unit FROM nutrient_codes "
        "WHERE nutrient_code = ANY(%s)",
        (codes,),
    )
    return {r["nutrient_code"]: r["kdri_unit"] for r in cur.fetchall()}


def _fetch_kdri_row(cur, code: str, age: int, g: str) -> Dict[str, Any] | None:
    # 정확 gender 우선(ALL은 후순위), 그다음 가장 좁은 연령 band.
    cur.execute(
        """
        SELECT ri_base, ul_limit, is_weight_scaled
        FROM kdri_standards
        WHERE nutrient_code = %s
          AND age_min <= %s AND age_max >= %s
          AND gender IN (%s, 'ALL')
        ORDER BY (gender = %s) DESC, (age_max - age_min) ASC
        LIMIT 1;
        """,
        (code, age, age, g, g),
    )
    return cur.fetchone()


def db_calculate_ri(
    age: int, gender: str, target_nutrients: List[str]
) -> Dict[str, Any]:
    """calculate_dynamic_ri MCP 출력 형태로 DB 기반 RI 산출.

    per-kg 계수 컬럼이 스키마에 없어 체중 스케일링은 미적용(value=ri_base).
    ponytail: 계수 테이블 생기면 value = base * factor * weight로 승격.
    """
    g = _gender_code(gender)
    custom_ri: Dict[str, Any] = {}
    with get_db_connection() as conn, conn.cursor() as cur:
        units = _fetch_units(cur, target_nutrients)
        for code in target_nutrients:
            row = _fetch_kdri_row(cur, code, age, g)
            if not row or row["ri_base"] is None:
                continue  # 매칭 없는 코드는 생략(0으로 처방하지 않음)
            base = float(row["ri_base"])
            custom_ri[code] = {
                "base": base,
                "factor_per_kg": None,
                "value": base,
                "unit": units.get(code, ""),
            }
    return {"custom_ri": custom_ri}


def db_search_products(target_nutrients: List[str], limit: int = 10) -> Dict[str, Any]:
    """product_ingredients_master(long format)를 제품 단위로 묶어 반환.

    타깃 영양소 커버리지 내림차순 랭킹. MCP search_products 출력 형태에 맞춤.
    """
    if not target_nutrients:
        return {"products": []}

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT product_id, product_name, nutrient_code, amount_per_serving, unit
            FROM product_ingredients_master
            WHERE nutrient_code = ANY(%s)
            """,
            (target_nutrients,),
        )
        rows = cur.fetchall()

    grouped: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        pid = r["product_id"]
        p = grouped.setdefault(pid, {
            "label_id": int(pid) if str(pid).isdigit() else None,
            "product_name": r["product_name"],
            "brand": None,   # 스키마에 brand/form 컬럼 없음
            "form": None,
            "nutrients": {},
        })
        p["nutrients"][r["nutrient_code"]] = float(r["amount_per_serving"])

    products = sorted(
        grouped.values(), key=lambda p: len(p["nutrients"]), reverse=True
    )
    return {"products": products[:limit]}


def db_validate_ul(
    proposed: Dict[str, float],
    current: Dict[str, float],
    diet: Dict[str, float],
    age: int,
    gender: str,
) -> Dict[str, Any]:
    """제안+현재+식이 합산 섭취를 각 영양소 UL과 대조. 초과 시 위반."""
    g = _gender_code(gender)
    codes = sorted(set(proposed) | set(current) | set(diet))
    violations: List[Dict[str, Any]] = []

    if codes:
        with get_db_connection() as conn, conn.cursor() as cur:
            for code in codes:
                row = _fetch_kdri_row(cur, code, age, g)
                ul = row and row["ul_limit"]
                if ul is None:
                    continue  # UL 없는 영양소는 검증 대상 아님
                total = (
                    proposed.get(code, 0)
                    + current.get(code, 0)
                    + diet.get(code, 0)
                )
                if total > float(ul):
                    violations.append({
                        "nutrient": code,
                        "total_intake": total,
                        "ul_limit": float(ul),
                        "status": "EXCEEDED",
                    })

    breached = {v["nutrient"] for v in violations}
    approved = [
        {"nutrient": c, "amount": a}
        for c, a in proposed.items()
        if c not in breached
    ]
    return {
        "is_safe": not violations,
        "ul_violations": violations,
        "approved_recommendations": approved,
    }
