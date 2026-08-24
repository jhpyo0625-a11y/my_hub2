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

# =============================================================================
# 회원 (users) — 회원가입 / 로그인
# -----------------------------------------------------------------------------
# 비밀번호는 **절대 평문으로 저장하지 않습니다.** bcrypt 해시만 넣고, 원문은
# 검증이 끝나는 즉시 버립니다(로그에도 남기지 않습니다).
#
# 위쪽 함수들과 마찬가지로 전부 동기 함수입니다. async 인 쪽(server.py)에서
# asyncio.to_thread 로 감싸 부릅니다 — 그러지 않으면 DB 가 느릴 때 서버
# 전체가 멈춥니다.
# =============================================================================
import bcrypt


class DuplicateUser(Exception):
    """이미 있는 아이디로 가입을 시도했습니다."""


# users.id 는 VARCHAR(100) 이지만 prescription_histories.user_id 는
# VARCHAR(50) 입니다. 50자를 넘는 아이디로 가입하면 그 사용자의 리포트
# 이력을 남길 수 없으므로, 짧은 쪽에 맞춰 미리 막습니다.
MAX_ID_LEN = 50
MAX_NAME_LEN = 100
MIN_PWD_LEN = 4


def hash_password(pwd: str) -> str:
    """bcrypt 해시. 출력은 60자라 VARCHAR(255) 에 넉넉히 들어갑니다."""
    return bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(pwd: str, pwd_hash: str) -> bool:
    """평문과 해시를 대조. 해시가 깨져 있어도 예외 대신 False 를 돌려줍니다."""
    try:
        return bcrypt.checkpw(pwd.encode("utf-8"), pwd_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False


# 아이디가 없을 때도 해시 검증을 한 번 수행해 응답 시간을 비슷하게 맞추기
# 위한 더미입니다. 이게 없으면 응답이 돌아오는 속도만으로 '그 아이디가
# 존재하는지'를 알아낼 수 있습니다.
_DUMMY_HASH = hash_password("dummy-password-for-timing")


def normalize_user_id(raw) -> str:
    """아이디 정규화. 대소문자와 앞뒤 공백 때문에 같은 사람이 둘로 갈리지
    않도록, 저장할 때도 찾을 때도 반드시 이 함수를 거칩니다."""
    return str(raw or "").strip().lower()


def validate_signup(user_id: str, pwd: str, name: str) -> str | None:
    """입력값이 규격에 맞는지. 문제가 있으면 사용자에게 보여 줄 문구를,
    없으면 None 을 돌려줍니다. DB 를 건드리지 않으므로 따로 테스트할 수
    있습니다."""
    if not user_id:
        return "아이디를 입력해주세요."
    if len(user_id) > MAX_ID_LEN:
        return f"아이디는 {MAX_ID_LEN}자 이하로 입력해주세요."
    if not (pwd or "").strip():
        return "비밀번호를 입력해주세요."
    if len(pwd) < MIN_PWD_LEN:
        return f"비밀번호는 {MIN_PWD_LEN}자 이상으로 입력해주세요."
    if not (name or "").strip():
        return "이름을 입력해주세요."
    if len(name.strip()) > MAX_NAME_LEN:
        return f"이름은 {MAX_NAME_LEN}자 이하로 입력해주세요."
    return None


def create_user(user_id: str, pwd: str, name: str) -> dict:
    """회원 한 명을 저장하고 {id, name} 을 돌려줍니다.

    중복 아이디는 **PK 제약에 맡깁니다.** '먼저 조회해 보고 없으면 넣기'는
    두 요청이 동시에 들어오면 둘 다 통과해 버립니다. INSERT 를 시도하고
    UniqueViolation 을 잡는 쪽이 안전합니다.
    """
    import psycopg.errors

    key = normalize_user_id(user_id)
    with get_db_connection() as conn, conn.cursor() as cur:
        try:
            cur.execute(
                """
                INSERT INTO users (id, pwd_hash, name)
                VALUES (%s, %s, %s)
                RETURNING id, name
                """,
                (key, hash_password(pwd), name.strip()),
            )
        except psycopg.errors.UniqueViolation:
            raise DuplicateUser(key)
        return dict(cur.fetchone())


def find_user(user_id: str) -> dict | None:
    """아이디로 한 명. 없으면 None. 해시를 함께 돌려주므로 호출한 쪽에서
    바로 verify_password 로 대조할 수 있습니다."""
    key = normalize_user_id(user_id)
    if not key:
        return None
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, pwd_hash, name FROM users WHERE id = %s",
            (key,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def authenticate(user_id: str, pwd: str) -> dict | None:
    """아이디와 비밀번호가 맞으면 {id, name}, 아니면 None.

    ★ '아이디가 없다' 와 '비밀번호가 틀렸다' 를 구분해서 돌려주지 않습니다.
      구분해서 알려 주면 어떤 아이디가 가입되어 있는지 확인하는 데
      쓰일 수 있습니다.
    """
    user = find_user(user_id)
    if user is None:
        # 없는 아이디여도 해시 검증을 한 번 돌려 응답 시간을 맞춥니다.
        verify_password(pwd or "", _DUMMY_HASH)
        return None
    if not verify_password(pwd or "", user["pwd_hash"]):
        return None
    return {"id": user["id"], "name": user["name"]}


def delete_user(user_id: str) -> int:
    """검증용 계정을 지울 때 씁니다. 지운 행 수를 돌려줍니다."""
    key = normalize_user_id(user_id)
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM users WHERE id = %s", (key,))
        return cur.rowcount

# =============================================================================
# 처방/검사 이력 (prescription_histories)
# =============================================================================

def get_prescription_histories(
    user_id: str,
) -> List[Dict[str, Any]]:
    """현재 로그인 사용자의 검사/추천 이력 목록을 조회합니다.

    prescription_histories와 user_health_presets를 user_id 기준으로
    조인하여 목록 화면에 필요한 사용자 건강 정보를 함께 반환합니다.
    """

    key = normalize_user_id(user_id)

    if not key:
        return []

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                ph.id,
                ph.title,
                ph.created_at,

                uhp.age,
                uhp.gender,
                uhp.weight_kg,
                uhp.activity_level,
                uhp.latest_checkup_data,
                uhp.routine_supplements,
                uhp.allergies_conditions,

                ph.output_report

            FROM prescription_histories ph

            INNER JOIN user_health_presets uhp
                ON ph.user_id = uhp.user_id

            WHERE ph.user_id = %s

            ORDER BY
                ph.created_at DESC NULLS LAST,
                ph.id DESC
            """,
            (key,),
        )

        rows = cur.fetchall()

    return [dict(row) for row in rows]


def get_prescription_history(
    user_id: str,
    history_id: int,
) -> Dict[str, Any] | None:
    """특정 사용자의 특정 처방/검사 이력 상세 정보를 조회합니다.

    history_id만으로 조회하지 않고 user_id를 함께 조건에 사용하여
    다른 사용자의 이력에 접근할 수 없도록 합니다.
    """

    key = normalize_user_id(user_id)

    if not key:
        return None

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                title,
                user_health_preset_id,
                output_report,
                created_at
            FROM prescription_histories
            WHERE id = %s
              AND user_id = %s
            LIMIT 1
            """,
            (history_id, key),
        )

        row = cur.fetchone()

    return dict(row) if row else None


def remove_prescription_history(
    user_id: str,
    history_id: int,
) -> bool:
    """특정 사용자의 특정 처방/검사 이력을 삭제합니다."""
    key = normalize_user_id(user_id)

    if not key:
        return False

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE
                FROM prescription_histories
                WHERE id = %s
                  AND user_id = %s
                """,
                (history_id, key),
            )
            deleted_rows = cur.rowcount
        conn.commit()

    return deleted_rows > 0

def get_user_health_presets(
    user_id: str,
    preset_id: int,
) -> Dict[str, Any] | None:
    """특정 사용자의 입력 정보를 조회합니다.

    preset_id만으로 조회하지 않고 user_id를 함께 조건에 사용하여
    다른 사용자의 입력 정보에 접근할 수 없도록 합니다.
    """

    key = normalize_user_id(user_id)

    if not key:
        return None

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                age,
                gender,
                weight_kg,
                activity_level,
                routine_supplements,
                latest_checkup_data,
                allergies_conditions,
                updated_at
            FROM user_health_presets
            WHERE id = %s
              AND user_id = %s
            LIMIT 1
            """,
            (preset_id, key),
        )

        row = cur.fetchone()

    return dict(row) if row else None

def save_user_health_presets(
    user_id: str,
    preset_id: int,
) -> Dict[str, Any] | None:
    """특정 사용자의 입력 정보를 조회합니다.

    preset_id만으로 조회하지 않고 user_id를 함께 조건에 사용하여
    다른 사용자의 입력 정보에 접근할 수 없도록 합니다.
    """

    key = normalize_user_id(user_id)

    if not key:
        return None

    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                age,
                gender,
                weight_kg,
                activity_level,
                routine_supplements,
                latest_checkup_data,
                allergies_conditions,
                updated_at
            FROM user_health_presets
            WHERE id = %s
              AND user_id = %s
            LIMIT 1
            """,
            (preset_id, key),
        )

        row = cur.fetchone()

    return dict(row) if row else None
