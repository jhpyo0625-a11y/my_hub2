"""Precision Nutrition MCP server (FastMCP).

`mcp_tools_specs.json`의 9개 tool을 FastMCP로 제공한다.
KDRI 기반 수치는 아래 curated 참조표에서 나온다(2025 한국인 영양소 섭취기준 성인 19+ 값).
제품/근거 검색은 DATABASE_URL이 있으면 Neon PostgreSQL을, 없으면 빈 결과를 준다.

실행: uv run python main.py           # streamable-http, http://localhost:8080/mcp/
      uv run python main.py --stdio   # stdio transport
      uv run python main.py --selftest

주의: FastMCP HTTP는 표준 MCP 프로토콜(streamable-http)이다. agent/services/mcp_client.py의
커스텀 JSON-RPC POST(/ 로 tools/<name>)는 그대로는 호출 불가 — 클라이언트를 MCP SDK로 교체 필요.
"""
from __future__ import annotations

import os
import sys

from fastmcp import FastMCP

try:
    from dotenv import load_dotenv  # optional
    load_dotenv()
except Exception:  # noqa: BLE001
    pass

PORT = int(os.getenv("MCP_PORT", "8080"))
mcp = FastMCP("Precision Nutrition & Supplement Server")
REFERENCE_WEIGHT_KG = 60.0  # 체중 스케일 기준체중. 코호트 바뀌면 튜닝 지점.

# --------------------------------------------------------------------------- #
# Curated 참조표 — 출처: 2025 한국인 영양소 섭취기준(KDRI), 성인 19+ (개발용 값).
# ri: 성별 무관 스칼라 또는 {"male":..,"female":..}. ul: None이면 상한 없음.
# weight_scaled=True인 영양소만 factor_per_kg로 체중 비례. (성인 미량영양소는 대부분 고정)
# --------------------------------------------------------------------------- #
KDRI = {
    "vitamin_a":        {"unit": "mcg RAE", "ri": {"male": 800, "female": 650}, "ul": 3000,  "weight_scaled": False},
    "vitamin_d":        {"unit": "mcg",     "ri": 10,                            "ul": 100,   "weight_scaled": False},
    "vitamin_e":        {"unit": "mg a-TE", "ri": 12,                            "ul": 540,   "weight_scaled": False},
    "vitamin_k":        {"unit": "mcg",     "ri": {"male": 75, "female": 65},    "ul": None,  "weight_scaled": False},
    "vitamin_c":        {"unit": "mg",      "ri": 100,                           "ul": 2000,  "weight_scaled": False},
    "thiamin":          {"unit": "mg",      "ri": {"male": 1.2, "female": 1.1},  "ul": None,  "weight_scaled": False},
    "riboflavin":       {"unit": "mg",      "ri": {"male": 1.5, "female": 1.2},  "ul": None,  "weight_scaled": False},
    "niacin":           {"unit": "mg NE",   "ri": {"male": 16, "female": 14},    "ul": 35,    "weight_scaled": False},
    "vitamin_b6":       {"unit": "mg",      "ri": {"male": 1.5, "female": 1.4},  "ul": 100,   "weight_scaled": False},
    "folate":           {"unit": "mcg DFE", "ri": 400,                           "ul": 1000,  "weight_scaled": False},
    "vitamin_b12":      {"unit": "mcg",     "ri": 2.4,                           "ul": None,  "weight_scaled": False},
    "pantothenic_acid": {"unit": "mg",      "ri": 5,                             "ul": None,  "weight_scaled": False},
    "biotin":           {"unit": "mcg",     "ri": 30,                            "ul": None,  "weight_scaled": False},
    "calcium":          {"unit": "mg",      "ri": {"male": 800, "female": 700},  "ul": 2500,  "weight_scaled": False},
    "phosphorus":       {"unit": "mg",      "ri": 700,                           "ul": 3500,  "weight_scaled": False},
    "magnesium":        {"unit": "mg",      "ri": {"male": 350, "female": 280},  "ul": 350,   "weight_scaled": False},
    "iron":             {"unit": "mg",      "ri": {"male": 10, "female": 14},    "ul": 45,    "weight_scaled": False},
    "zinc":             {"unit": "mg",      "ri": {"male": 10, "female": 8},     "ul": 35,    "weight_scaled": False},
    "copper":           {"unit": "mcg",     "ri": {"male": 850, "female": 650},  "ul": 10000, "weight_scaled": False},
    "manganese":        {"unit": "mg",      "ri": {"male": 4.0, "female": 3.5},  "ul": 11,    "weight_scaled": False},
    "iodine":           {"unit": "mcg",     "ri": 150,                           "ul": 2400,  "weight_scaled": False},
    "selenium":         {"unit": "mcg",     "ri": 60,                            "ul": 400,   "weight_scaled": False},
    "molybdenum":       {"unit": "mcg",     "ri": {"male": 30, "female": 25},    "ul": 550,   "weight_scaled": False},
    "chromium":         {"unit": "mcg",     "ri": {"male": 35, "female": 25},    "ul": None,  "weight_scaled": False},
    "potassium":        {"unit": "mg",      "ri": 3500,                          "ul": None,  "weight_scaled": False},
    "protein":          {"unit": "g",       "ri": 55,   "factor_per_kg": 0.91,   "ul": None,  "weight_scaled": True},
}

# 길항 쌍(같은 시간 복용 피함) — 스케줄 2색 분리 대상.
ANTAGONISTS = [
    ("calcium", "iron"),
    ("calcium", "zinc"),
    ("zinc", "copper"),
    ("iron", "zinc"),
    ("calcium", "magnesium"),
]
ANTAGONIST_NOTE = {
    ("calcium", "iron"): "칼슘은 철분 흡수를 방해 — 2시간 이상 시차 복용 권장",
    ("calcium", "zinc"): "칼슘과 아연은 흡수 경쟁 — 시차 복용 권장",
    ("zinc", "copper"): "고용량 아연은 구리 흡수를 억제 — 시차 복용 권장",
    ("iron", "zinc"): "철분과 아연은 흡수 경쟁 — 시차 복용 권장",
    ("calcium", "magnesium"): "칼슘과 마그네슘 고용량 동시 복용 시 흡수 저하 가능",
}

# 검사명 -> (단위, low_max, high_min). value < low_max=low, >= high_min=high, else normal.
LAB_RANGES = {
    "ldl":               ("mg/dL", None, 130),
    "hdl":               ("mg/dL", 40,   None),
    "total_cholesterol": ("mg/dL", None, 200),
    "triglycerides":     ("mg/dL", None, 150),
    "glucose":           ("mg/dL", 70,   100),
    "hba1c":             ("%",     4.0,  5.7),
    "vitamin_d":         ("ng/mL", 20,   100),
}
LAB_SYNONYMS = {
    "ldl-c": "ldl", "ldl cholesterol": "ldl", "저밀도콜레스테롤": "ldl",
    "hdl-c": "hdl", "hdl cholesterol": "hdl", "고밀도콜레스테롤": "hdl",
    "cholesterol": "total_cholesterol", "총콜레스테롤": "total_cholesterol", "tc": "total_cholesterol",
    "tg": "triglycerides", "중성지방": "triglycerides",
    "fasting glucose": "glucose", "혈당": "glucose", "공복혈당": "glucose", "fbs": "glucose",
    "a1c": "hba1c", "당화혈색소": "hba1c",
    "25-oh-d": "vitamin_d", "비타민d": "vitamin_d", "vitamin d": "vitamin_d",
}

# 코호트 성인 중앙 체중 (Korean adult, 개발용).
COHORT_WEIGHT = {"male": 68.7, "female": 56.6}

# 자유텍스트 -> nutrient_code. 정규화(소문자/공백/하이픈 제거) 후 매칭.
NUTRIENT_SYNONYMS = {
    "비타민c": "vitamin_c", "vitaminc": "vitamin_c", "vitc": "vitamin_c", "아스코르브산": "vitamin_c", "비타민씨": "vitamin_c",
    "비타민d": "vitamin_d", "vitamind": "vitamin_d", "vitd": "vitamin_d", "콜레칼시페롤": "vitamin_d", "비타민디": "vitamin_d",
    "비타민a": "vitamin_a", "vitamina": "vitamin_a", "레티놀": "vitamin_a",
    "비타민e": "vitamin_e", "vitamine": "vitamin_e", "토코페롤": "vitamin_e",
    "비타민k": "vitamin_k", "vitamink": "vitamin_k",
    "비타민b12": "vitamin_b12", "vitaminb12": "vitamin_b12", "b12": "vitamin_b12", "코발라민": "vitamin_b12",
    "비타민b6": "vitamin_b6", "vitaminb6": "vitamin_b6", "b6": "vitamin_b6", "피리독신": "vitamin_b6",
    "티아민": "thiamin", "비타민b1": "thiamin", "b1": "thiamin",
    "리보플라빈": "riboflavin", "비타민b2": "riboflavin", "b2": "riboflavin",
    "니아신": "niacin", "비타민b3": "niacin", "나이아신": "niacin",
    "엽산": "folate", "폴산": "folate", "folicacid": "folate", "비타민b9": "folate",
    "판토텐산": "pantothenic_acid", "비타민b5": "pantothenic_acid",
    "비오틴": "biotin", "비타민b7": "biotin",
    "칼슘": "calcium", "ca": "calcium",
    "인": "phosphorus",
    "마그네슘": "magnesium", "mg": "magnesium",
    "철": "iron", "철분": "iron", "fe": "iron",
    "아연": "zinc", "zn": "zinc",
    "구리": "copper", "cu": "copper",
    "망간": "manganese",
    "요오드": "iodine", "아이오딘": "iodine",
    "셀레늄": "selenium", "셀렌": "selenium",
    "몰리브덴": "molybdenum",
    "크롬": "chromium",
    "칼륨": "potassium",
    "단백질": "protein",
}


def _norm(s: str) -> str:
    return "".join(str(s).lower().split()).replace("-", "").replace("_", "")


def _ri_base(code: str, gender: str) -> float | None:
    spec = KDRI.get(code)
    if not spec:
        return None
    ri = spec["ri"]
    if isinstance(ri, dict):
        return float(ri.get("male" if gender == "male" else "female"))
    return float(ri)


# --------------------------------------------------------------------------- #
# DB (선택). 없거나 실패하면 빈 결과로 우아하게 강등.
# --------------------------------------------------------------------------- #
def _db_conn():
    url = os.getenv("DATABASE_URL")
    if not url:
        return None
    import psycopg  # lazy
    from psycopg.rows import dict_row
    return psycopg.connect(url, row_factory=dict_row)


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
def calculate_dynamic_ri(age: int, gender: str, weight_kg: float, target_nutrients: list[str]) -> dict:
    """Compute the weight-adjusted recommended daily intake (RI) for each target nutrient.

    Derives personalized dose targets from the user's age, gender, and body weight against
    the 2025 KDRI reference table (Korean adults 19+). Weight-scaled nutrients (e.g. protein)
    are multiplied by a per-kg factor; the rest use the fixed KDRI base for the sex bracket.
    Call this FIRST, once the target nutrients are known, to establish dose targets before
    recommending anything.

    Args:
        age: Age in years.
        gender: "male"/"female" (any string starting with "m" is treated as male).
        weight_kg: Body weight in kilograms.
        target_nutrients: nutrient_code list to compute RIs for.

    Returns:
        {"custom_ri": {nutrient_code: {base, factor_per_kg, value, unit}}}. A code with no
        matching KDRI row is omitted from the map (never dosed at 0). `factor_per_kg` is null
        for non-weight-scaled nutrients; `value` is the final personalized RI in `unit`.
    """
    gender = "male" if str(gender).lower().startswith("m") else "female"
    weight_kg = float(weight_kg)
    custom_ri = {}
    for code in target_nutrients or []:
        spec = KDRI.get(code)
        base = _ri_base(code, gender)
        if spec is None or base is None:
            continue  # 매칭 base 없으면 생략(0으로 투여하지 않음)
        if spec.get("weight_scaled"):
            factor = spec.get("factor_per_kg", base / REFERENCE_WEIGHT_KG)
            value = round(factor * weight_kg, 3)
        else:
            factor = None
            value = base
        custom_ri[code] = {"base": base, "factor_per_kg": factor, "value": value, "unit": spec["unit"]}
    return {"custom_ri": custom_ri}


def validate_ul_guardrail(current_supps_intake: dict[str, float], diet_estimated_intake: dict[str, float],
                          proposed_supps_intake: dict[str, float],
                          age: int, gender: str, weight_kg: float) -> dict:
    """Enforce Tolerable Upper Intake Level (UL) safety across combined intake.

    Sums current supplements + estimated diet + proposed supplements per nutrient and checks
    each total against its KDRI UL. Returns the safe subset of proposed items with any
    violations. Call this LAST, once a proposed supplement set exists, before finalizing —
    it is the guardrail that guarantees no recommendation pushes a nutrient over its UL.

    Args:
        current_supps_intake: nutrient_code -> amount (KDRI unit) from existing supplements.
        diet_estimated_intake: nutrient_code -> estimated amount from diet.
        proposed_supps_intake: nutrient_code -> amount from the recommendations being validated.
        age, gender, weight_kg: user profile (currently informational; UL is bracket-independent).

    Returns:
        {"is_safe": bool, "ul_violations": [{nutrient, total_intake, ul_limit, status:"EXCEEDED"}],
         "approved_recommendations": [{nutrient, amount}]}. `is_safe` is True only when no total
        exceeds its UL. Nutrients with no UL (ul=None) are never flagged. Any proposed nutrient
        that breaches its UL is dropped from `approved_recommendations`.
    """
    current_supps_intake = current_supps_intake or {}
    diet_estimated_intake = diet_estimated_intake or {}
    proposed_supps_intake = proposed_supps_intake or {}
    codes = set(current_supps_intake) | set(diet_estimated_intake) | set(proposed_supps_intake)

    violations = []
    breached = set()
    for code in codes:
        spec = KDRI.get(code)
        ul = spec["ul"] if spec else None
        if ul is None:
            continue
        total = (float(current_supps_intake.get(code, 0))
                 + float(diet_estimated_intake.get(code, 0))
                 + float(proposed_supps_intake.get(code, 0)))
        if total > ul:
            violations.append({"nutrient": code, "total_intake": round(total, 3),
                               "ul_limit": ul, "status": "EXCEEDED"})
            breached.add(code)

    approved = [{"nutrient": code, "amount": float(amt)}
                for code, amt in proposed_supps_intake.items() if code not in breached]
    return {"is_safe": not violations, "ul_violations": violations, "approved_recommendations": approved}


def check_nutrient_interactions(nutrient_list: list[str]) -> dict:
    """Split nutrients into an AM/PM schedule that separates antagonistic pairs.

    Looks up known antagonist pairs (e.g. calcium/iron, zinc/copper) among the given nutrients,
    then 2-colors the conflict graph via BFS to produce a morning/evening schedule where
    competing pairs never share a slot. Call after choosing which nutrients to recommend.

    Args:
        nutrient_list: nutrient_code list to schedule and check.

    Returns:
        {"conflicts_found": bool, "time_separated_schedule": {"morning_AM": [...],
         "evening_PM": [...]}, "cautions": [str]}. `cautions` carries human-readable interaction
        notes; when an odd-cycle conflict cannot be perfectly 2-colored it adds a best-effort
        caution and still returns a schedule.
    """
    present = [n for n in (nutrient_list or [])]
    pset = set(present)
    edges = [(a, b) for a, b in ANTAGONISTS if a in pset and b in pset]
    cautions = [ANTAGONIST_NOTE[(a, b)] for a, b in edges]

    # 인접 리스트 만들고 BFS 2색 분리. 홀수 사이클이면 best-effort + caution.
    adj = {n: set() for n in present}
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    color = {}
    imperfect = False
    for start in present:
        if start in color:
            continue
        color[start] = 0
        queue = [start]
        while queue:
            node = queue.pop()
            for nb in adj[node]:
                if nb not in color:
                    color[nb] = 1 - color[node]
                    queue.append(nb)
                elif color[nb] == color[node]:
                    imperfect = True
    am = [n for n in present if color.get(n, 0) == 0]
    pm = [n for n in present if color.get(n, 0) == 1]
    if imperfect:
        cautions.append("일부 길항 관계는 오전/오후 2분할로 완전히 분리되지 않음 — 복용 간격을 최대한 두세요.")
    return {"conflicts_found": bool(edges),
            "time_separated_schedule": {"morning_AM": am, "evening_PM": pm},
            "cautions": cautions}


def normalize_medical_data(raw_lab_results: list[dict]) -> dict:
    """Standardize raw lab-test values and flag each low/normal/high.

    Matches each test name (case-insensitive, with synonym aliases like "ldl-c"->"ldl",
    "당화혈색소"->"hba1c") to a reference range and flags the value. Call when the user provides
    health-checkup numbers (OCR'd or typed) that need interpretation before profiling.

    Args:
        raw_lab_results: list of {"test_name": str, "value": number, "unit": str}.
            test_name is matched case-insensitively (e.g. LDL, HDL, glucose, vitamin D).

    Returns:
        {"results": [{test_name, value, unit, flag}]} where flag is "low"/"normal"/"high".
        Tests with no known reference range are passed through as "normal" (judgment withheld).
    """
    results = []
    for row in raw_lab_results or []:
        name_raw = str(row.get("test_name", ""))
        key = LAB_SYNONYMS.get(name_raw.lower().strip(), name_raw.lower().strip())
        rng = LAB_RANGES.get(key)
        value = float(row.get("value"))
        if rng is None:
            flag = "normal"  # 참조범위 없는 검사는 판정 보류
        else:
            _, low_max, high_min = rng
            if low_max is not None and value < low_max:
                flag = "low"
            elif high_min is not None and value >= high_min:
                flag = "high"
            else:
                flag = "normal"
        results.append({"test_name": row.get("test_name"), "value": value,
                        "unit": row.get("unit"), "flag": flag})
    return {"results": results}


def resolve_nutrient_codes(names: list[str]) -> dict:
    """Resolve free-text nutrient names (Korean or English) to canonical nutrient_code values.

    Normalizes each input (lowercase, strip spaces/hyphens/underscores) and matches it against
    the KDRI code set (exact) then the synonym table (e.g. "철분"->iron, "비타민C"->vitamin_c).
    Call once up front, in the Normalizer step, to turn the user's supplement list and abnormal
    lab signals into nutrient_code strings before any other tool runs.

    Args:
        names: free-text nutrient/supplement names.

    Returns:
        {"resolved": [{input, nutrient_code, matched_synonym, confidence}]}. `confidence` is
        "exact" (input was already a code), "synonym" (matched an alias), or "none"
        (unrecognized — nutrient_code and matched_synonym are null).
    """
    resolved = []
    for name in names or []:
        code_form = str(name).strip().lower()
        n = _norm(name)
        if code_form in KDRI:  # 입력이 코드 그 자체
            resolved.append({"input": name, "nutrient_code": code_form,
                             "matched_synonym": code_form, "confidence": "exact"})
        elif n in NUTRIENT_SYNONYMS:
            code = NUTRIENT_SYNONYMS[n]
            resolved.append({"input": name, "nutrient_code": code,
                             "matched_synonym": n, "confidence": "synonym"})
        else:
            resolved.append({"input": name, "nutrient_code": None,
                             "matched_synonym": None, "confidence": "none"})
    return {"resolved": resolved}


def fill_missing_profile(age: int, gender: str, weight_kg: float | None = None,
                         current_intake: dict[str, float] | None = None,
                         target_nutrients: list[str] | None = None) -> dict:
    """Fill missing weight and current-intake fields with cohort defaults, reporting each estimate.

    When the user omits weight, substitutes the cohort median weight for their sex. When a target
    nutrient is missing from current_intake, substitutes the cohort RI base for it. Every
    substitution is recorded in `advisory` so downstream steps know which numbers were estimated
    rather than user-provided. Call in the Normalizer step when weight or current intake is absent.

    Args:
        age: Age in years.
        gender: "male"/"female" (any string starting with "m" is treated as male).
        weight_kg: Body weight in kg, or None to fill from the cohort median-weight table.
        current_intake: nutrient_code -> current amount, or None; missing targets are filled.
        target_nutrients: nutrient_codes to ensure a current_intake value exists for.

    Returns:
        {"filled": {"weight_kg": number, "current_intake": {code: number}},
         "advisory": [str]}. `advisory` lists exactly what was estimated and how.
    """
    gender = "male" if str(gender).lower().startswith("m") else "female"
    advisory = []
    if weight_kg is None:
        weight_kg = COHORT_WEIGHT[gender]
        advisory.append(f"체중 미입력 — 코호트 중앙값 {weight_kg}kg({gender})로 추정")
    weight_kg = float(weight_kg)

    current_intake = dict(current_intake or {})
    for code in target_nutrients or []:
        if code not in current_intake:
            base = _ri_base(code, gender)
            if base is None:
                continue
            current_intake[code] = base
            advisory.append(f"{code} 현재 섭취 미입력 — 코호트 RI 기준 {base}로 추정")
    return {"filled": {"weight_kg": weight_kg, "current_intake": current_intake}, "advisory": advisory}


def compute_intake_coverage(intake: dict[str, float], custom_ri: dict) -> dict:
    """Classify each nutrient's intake as deficient/adequate/excess vs its personalized RI.

    Divides intake by the RI to get a coverage percentage, then buckets it: <90% deficient,
    >150% excess, otherwise adequate. Call in the Reviewer step after a UL check to detect
    whether dropping a UL-breaching product left any target nutrient deficient; the result also
    feeds the Aggregator's intake visualization.

    Args:
        intake: nutrient_code -> summed (current+diet+proposed) amount.
        custom_ri: nutrient_code -> RI, accepting either a plain number or the
            {"value": number, ...} object returned by calculate_dynamic_ri.

    Returns:
        {"coverage": {nutrient_code: {"pct": number, "status": "deficient"|"adequate"|"excess"}}}.
        Codes with a non-positive RI are skipped.
    """
    # custom_ri는 code->숫자 또는 code->{"value":..} 둘 다 허용.
    intake = intake or {}
    coverage = {}
    for code, ri in (custom_ri or {}).items():
        ri_val = ri.get("value") if isinstance(ri, dict) else ri
        ri_val = float(ri_val or 0)
        if ri_val <= 0:
            continue
        pct = round(float(intake.get(code, 0)) / ri_val * 100, 1)
        if pct < 90:
            status = "deficient"
        elif pct > 150:  # 임계값 튜닝 지점
            status = "excess"
        else:
            status = "adequate"
        coverage[code] = {"pct": pct, "status": status}
    return {"coverage": coverage}


def search_products(target_nutrients: list[str], filters: dict | None = None) -> dict:
    """Find supplement products supplying the target nutrients, ranked by coverage.

    Queries the product_ingredients_master catalog (Neon PostgreSQL) for products whose
    nutrients overlap the targets, optionally filtered by dosage form and excluded ingredients,
    and ranks results by how many target nutrients each covers. Call after target RIs are known,
    to pick concrete products. Requires DATABASE_URL — returns {"products": []} when the DB is
    unset or unreachable (graceful degradation, never raises).

    Args:
        target_nutrients: nutrient_code list the product should supply.
        filters: optional {"form": substring (ILIKE, e.g. "capsule"),
            "exclude": [nutrient_codes to avoid]}.

    Returns:
        {"products": [{label_id, product_name, brand, form, nutrients}]}, up to 50, ranked by
        target coverage descending. `nutrients` is nutrient_code -> per-serving amount (KDRI unit).
    """
    filters = filters or {}
    form = filters.get("form")
    exclude = set(filters.get("exclude") or [])
    targets = [t for t in (target_nutrients or []) if t not in exclude]
    if not targets:
        return {"products": []}
    conn = _db_conn()
    if conn is None:
        return {"products": []}
    try:
        with conn, conn.cursor() as cur:
            placeholders = ", ".join(["%s"] * len(targets))
            sql = f"""
                SELECT label_id, product_name, brand, form, nutrients
                FROM product_ingredients_master
                WHERE EXISTS (
                    SELECT 1 FROM jsonb_object_keys(nutrients) k WHERE k IN ({placeholders})
                )
                {'AND form ILIKE %s' if form else ''}
                LIMIT 200;
            """
            params = list(targets) + ([f"%{form}%"] if form else [])
            cur.execute(sql, params)
            rows = cur.fetchall()
    except Exception as e:  # noqa: BLE001
        print(f"[search_products] DB 조회 실패, 빈 결과: {e}", file=sys.stderr)
        return {"products": []}

    products = []
    for r in rows:
        nutrients = r.get("nutrients") or {}
        if exclude & set(nutrients):
            continue
        coverage = sum(1 for t in targets if t in nutrients)
        products.append({"label_id": r["label_id"], "product_name": r["product_name"],
                         "brand": r.get("brand"), "form": r.get("form"),
                         "nutrients": {k: float(v) for k, v in nutrients.items()},
                         "_coverage": coverage})
    products.sort(key=lambda p: p.pop("_coverage"), reverse=True)
    return {"products": products[:50]}


def search_evidence(query: str, nutrient_code: str | None = None, k: int = 5) -> dict:
    """Retrieve cited nutrition/interaction evidence passages semantically similar to a query.

    Embeds the query (OpenAI embeddings) and runs a pgvector nearest-neighbor search over the
    evidence_chunks table, returning the top-k most similar passages with their citations. Call
    to ground an explanation or recommendation with a source. Requires DATABASE_URL and
    OPENAI_API_KEY — returns {"chunks": []} when either is missing or the lookup fails.

    Args:
        query: natural-language search query (Korean or English).
        nutrient_code: accepted for forward-compat but NOT used to filter (chunks have null
            nutrient_code).
        k: number of top passages to return (default 5).

    Returns:
        {"chunks": [{content, source, citation, url}]}, ordered by ascending cosine distance
        (most similar first).
    """
    conn = _db_conn()
    if conn is None or not os.getenv("OPENAI_API_KEY"):
        return {"chunks": []}
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL") or None)
        emb = client.embeddings.create(
            model=os.getenv("EMBED_MODEL", "text-embedding-3-small"),
            input=query,
        ).data[0].embedding
        vec = "[" + ",".join(str(x) for x in emb) + "]"
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT content, source, citation, url
                FROM evidence_chunks
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
                """,
                (vec, int(k)),
            )
            rows = cur.fetchall()
        return {"chunks": [{"content": r["content"], "source": r.get("source"),
                            "citation": r.get("citation"), "url": r.get("url")} for r in rows]}
    except Exception as e:  # noqa: BLE001
        print(f"[search_evidence] 실패, 빈 결과: {e}", file=sys.stderr)
        return {"chunks": []}


# FastMCP 등록. mcp.tool(fn)은 Tool을 반환만 하고 전역 이름은 순수 함수로 남아 selftest에서 직접 호출 가능.
for _fn in (calculate_dynamic_ri, validate_ul_guardrail, check_nutrient_interactions,
            normalize_medical_data, resolve_nutrient_codes, fill_missing_profile,
            compute_intake_coverage, search_products, search_evidence):
    mcp.tool(_fn)


def _selftest():
    ri = calculate_dynamic_ri(35, "female", 55, ["iron", "vitamin_d", "unknown_x"])["custom_ri"]
    assert ri["iron"]["value"] == 14 and ri["iron"]["unit"] == "mg", ri
    assert "unknown_x" not in ri, "매칭 없는 코드는 생략돼야 함"

    ul = validate_ul_guardrail({"iron": 20}, {"iron": 15}, {"iron": 20}, 35, "female", 55)
    assert ul["is_safe"] is False and ul["ul_violations"][0]["nutrient"] == "iron", ul
    assert ul["approved_recommendations"] == [], "UL 초과 기여분은 승인에서 제외"

    sched = check_nutrient_interactions(["calcium", "iron", "vitamin_c"])
    assert sched["conflicts_found"] is True
    assert set(sched["time_separated_schedule"]["morning_AM"]) & {"calcium", "iron"}
    assert not ({"calcium", "iron"} <= set(sched["time_separated_schedule"]["morning_AM"])), "길항쌍은 분리"

    lab = normalize_medical_data([{"test_name": "LDL", "value": 160, "unit": "mg/dL"}])["results"][0]
    assert lab["flag"] == "high", lab

    rc = resolve_nutrient_codes(["철분", "vitamin_d", "듣보잡"])["resolved"]
    assert rc[0]["nutrient_code"] == "iron" and rc[0]["confidence"] == "synonym"
    assert rc[1]["confidence"] == "exact" and rc[2]["confidence"] == "none"

    fp = fill_missing_profile(40, "male", None, {}, ["calcium"])
    assert fp["filled"]["weight_kg"] == COHORT_WEIGHT["male"]
    assert fp["filled"]["current_intake"]["calcium"] == 800 and fp["advisory"]

    cov = compute_intake_coverage({"iron": 7}, {"iron": {"value": 14}})["coverage"]
    assert cov["iron"]["pct"] == 50.0 and cov["iron"]["status"] == "deficient", cov
    print("selftest OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    elif "--stdio" in sys.argv:
        mcp.run()  # stdio transport
    else:
        mcp.run(transport="http", host="0.0.0.0", port=PORT)
