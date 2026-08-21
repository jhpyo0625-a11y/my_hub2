import os
import psycopg
from psycopg.rows import dict_row
from typing import Any, Dict, List

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """
    Neon PostgreSQL 커넥션을 리턴합니다.
    """
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL 환경 변수가 .env에 설정되어 있지 않습니다.")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

async def query_kdri_standard(nutrient_code: str, age: int, gender: str) -> Dict[str, Any]:
    """
    neondb의 schema_kdri_standards 테이블에 매치되는 ri_base, ul_limit 정보를 조회해옵니다.
    """
    # gender mapping
    g = "male" if gender.lower() in ["male", "m", "남성", "남자"] else "female"
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ri_base, ul_limit, is_weight_scaled
                FROM kdri_standards
                WHERE nutrient_code = %s
                  AND age_min <= %s
                  AND age_max >= %s
                  AND gender = %s
                LIMIT 1;
                """,
                (nutrient_code, age, age, g)
            )
            row = cur.fetchone()
            if row:
                return {
                    "ri_base": float(row["ri_base"]) if row["ri_base"] is not None else None,
                    "ul_limit": float(row["ul_limit"]) if row["ul_limit"] is not None else None,
                    "is_weight_scaled": bool(row["is_weight_scaled"])
                }
            return {}

async def search_products_by_nutrients(target_nutrients: List[str]) -> List[Dict[str, Any]]:
    """
    neondb에서 주어진 영양소들을 포함하는 제품들을 조회해옵니다.
    """
    if not target_nutrients:
        return []
        
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # target_nutrients 가 포함되어 있는 제품 정보를 master 테이블에서 쿼리하는 예시 쿼리
            # 실제 스키마가 로드되어 있는 프로덕션 환경의 쿼리 형식을 취함
            placeholders = ", ".join(["%s"] * len(target_nutrients))
            query = f"""
                SELECT label_id, product_name, brand, form, nutrients
                FROM product_ingredients_master
                WHERE exists (
                    SELECT 1 FROM jsonb_object_keys(nutrients) k WHERE k IN ({placeholders})
                )
                LIMIT 10;
            """
            cur.execute(query, tuple(target_nutrients))
            return cur.fetchall()
