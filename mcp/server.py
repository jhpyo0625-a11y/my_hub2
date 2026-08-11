"""MCP surface over the *real* KDRI 2025 engine.

This server exposes the deterministic engine in `backend/src/kdri` to external
agents. It computes NOTHING itself: every number comes from `compute_report`,
which reads the seeded KDRI vendor tables and cited curated files. That is the
whole product rule (see ../CLAUDE.md): the engine computes, an LLM never
produces a number, and there is no body-weight/BMR path (the 2025 기준 has no
weight-based micronutrient value). Missing diet baselines surface as UNKNOWN
rather than a guessed number, and sex is required — it can never be defaulted
(iron F 12 ≠ M 8).

Run: `uv run python server.py` (needs pyyaml + the kdri package on sys.path,
wired below).
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Reach the sibling backend package without installing it (mirrors the repo's
# "ad-hoc scripts need src on the path" convention). kdri resolves its own data
# dir from __file__, so cwd does not matter.
_BACKEND_SRC = Path(__file__).resolve().parent.parent / "backend" / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from fastmcp import FastMCP  # noqa: E402

from kdri.engine import compute_report  # noqa: E402
from kdri.loader import load_nutrients, load_profiles  # noqa: E402
from kdri.lookup import BandNotFound, find_band, resolve_limit  # noqa: E402
from kdri.models import Biomarker, Profile, SupplementIntake  # noqa: E402
from kdri.seed import load_engine_inputs  # noqa: E402

MIN_ADULT_AGE = 19

mcp = FastMCP("KDRI 2025 Nutrition Engine")

# Load the honest production inputs once (demo=False -> null diet baselines stay
# null -> the engine returns UNKNOWN instead of a guessed diet contribution).
INPUTS = load_engine_inputs(demo=False)


def _serialize(result, user: Profile) -> Dict[str, Any]:
    code = result.nutrient_code
    prof = INPUTS.profiles.get(code)
    nut = INPUTS.nutrients.get(code)
    target_unit = prof.target_unit if prof else ""
    ul_unit = prof.ul_unit if prof else "unknown"

    declared = [s.form_ko for s in user.supplements if s.nutrient_code == code]
    limit = None
    try:
        band = find_band(INPUTS.bands, code, user.sex, user.age)
        lim = resolve_limit(
            INPUTS.limits, band, code, declared, user.age, user.sex, ul_unit
        )
        if lim is not None:
            limit = {
                "value": lim.value,
                "unit": lim.unit,
                "basis": lim.basis,
                "source": lim.source,
            }
    except BandNotFound:
        pass

    flag = result.biomarker_flag
    return {
        "nutrient_code": code,
        "nutrient_ko": nut.name_ko if nut else code,
        "status": result.status,
        "target": result.target,
        "target_unit": target_unit,
        "from_diet": result.from_diet,
        "from_supplements": result.from_supplements,
        "gap": result.gap,
        "headroom": result.headroom,
        "recommend": result.recommend,
        "limit": limit,
        "biomarker_flag": (
            {
                "biomarker_code": flag.biomarker_code,
                "value": flag.value,
                "unit": flag.unit,
                "threshold": flag.threshold,
                "direction": flag.direction,
                "source": flag.source,
            }
            if flag is not None
            else None
        ),
    }


@mcp.tool()
async def analyze_intake_against_kdri(
    age: Optional[int] = None,
    sex: Optional[str] = None,
    supplements: Optional[List[Dict[str, Any]]] = None,
    medications: Optional[List[str]] = None,
    biomarkers: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run the KDRI 2025 engine over an adult profile and return, per nutrient,
    the target (from the national bands), diet/supplement contributions, the
    remaining gap, the upper-limit headroom, and a recommended top-up.

    The engine — not this tool — produces every number, and each traces to the
    seeded KDRI tables or a cited curated file. Where a nutrient's average diet
    contribution is not yet sourced, its status is UNKNOWN and no number is
    recommended (guessing would systematically over-recommend).

    Refuses rather than guesses: `sex` is required (M/F) and cannot be defaulted;
    `age` must be an adult (19+). Pregnancy/lactation are out of scope upstream.

    :param age: age in years (>= 19)
    :param sex: 'M' or 'F' — required, never defaulted
    :param supplements: [{nutrient_code, dose, doses_per_day?, form_ko?}, ...]
    :param biomarkers: [{code, value, unit?}, ...] — prioritizes, never re-targets
    """
    if sex not in ("M", "F"):
        return {
            "status": "refused",
            "code": "SEX_REQUIRED",
            "message": "성별(M/F)은 필수이며 기본값을 적용할 수 없습니다. "
            "성인 섭취기준은 성별로 나뉩니다 (예: 철 여성 12mg vs 남성 8mg).",
        }
    if age is None or age < MIN_ADULT_AGE:
        return {
            "status": "refused",
            "code": "AGE_OUT_OF_SCOPE",
            "message": "만 19세 이상 성인만 계산합니다. 소아·청소년은 별도 기준입니다.",
        }

    supplements = supplements or []
    biomarkers = biomarkers or []
    for s in supplements:
        if s.get("nutrient_code") not in INPUTS.in_scope:
            return {
                "status": "refused",
                "code": "INVALID_INTAKE",
                "message": f"알 수 없는 영양소 코드입니다: {s.get('nutrient_code')}",
            }

    user = Profile(
        age=age,
        sex=sex,
        supplements=tuple(
            SupplementIntake(
                nutrient_code=s["nutrient_code"],
                dose=float(s["dose"]),
                doses_per_day=float(s.get("doses_per_day", 1.0)),
                form_ko=s.get("form_ko"),
            )
            for s in supplements
        ),
        medications=tuple(medications or []),
        biomarkers=tuple(
            Biomarker(code=b["code"], value=float(b["value"]), unit=b.get("unit"))
            for b in biomarkers
            if b.get("value") is not None
        ),
    )

    results = compute_report(
        user, INPUTS.bands, INPUTS.limits, INPUTS.profiles, INPUTS.biomarker_refs
    )
    serialized = [_serialize(r, user) for r in results]

    # Surface any drug interactions from the cited curated table (context only —
    # they do not change a number).
    meds = set(user.medications)
    interactions = [
        {
            "nutrient_code": row["nutrient_code"],
            "drug_class": row["drug_class"],
            "severity": row["severity"],
            "action": row["action"],
            "source": row["source"],
        }
        for row in INPUTS.interactions
        if row["drug_class"] in meds
    ]

    summary = {"over": 0, "deficit": 0, "adequate": 0, "unknown": 0}
    for r in serialized:
        summary[r["status"].lower()] += 1

    return {
        "status": "ok",
        "kdri_version": "2025",
        "summary": summary,
        "results": serialized,
        "interactions": interactions,
        "note": "모든 수치는 KDRI 2025 기준·근거에서 계산되었습니다. "
        "식이 기여 기준이 없는 항목은 UNKNOWN으로 남겨 과대 추천을 막습니다.",
    }


# IU→metric conversion factors are standard vitamin equivalences, cited inline.
_IU_CONVERSIONS = {
    "vitamin_d": (40.0, "1 µg = 40 IU (cholecalciferol)"),
    "vitamin_a": (3.33, "1 µg RAE = 3.33 IU (retinol)"),
    "vitamin_e": (1.49, "1 mg α-TE = 1.49 IU (RRR-α-tocopherol)"),
}


def _clean_unit(u: str) -> str:
    u = (u or "").lower().strip().replace(" ", "")
    if u in ("ug", "㎍", "mcg", "µg"):
        return "μg"
    return u


@mcp.tool()
async def normalize_supplement_component(
    nutrient_code: str, current_value: float, current_unit: str
) -> Dict[str, Any]:
    """Compare a supplement label's unit to the KDRI 2025 standard unit for that
    nutrient and, where a well-defined equivalence exists, convert the value.

    The standard unit is read from the real nutrient profiles (single source of
    truth), not a hand-copied table. Handles IU→metric for vitamins A/D/E and
    plain mass rescaling (g↔mg↔µg). Anything else is reported as unconvertible
    rather than guessed.
    """
    code = nutrient_code.lower().strip()
    profiles = load_profiles()
    nutrients = load_nutrients()
    prof = profiles.get(code)
    nut = nutrients.get(code)
    if prof is None or nut is None:
        return {
            "status": "error",
            "message": f"영양소 코드 '{nutrient_code}'는 표준 규격에 없습니다.",
        }

    standard_unit = prof.target_unit
    in_u = _clean_unit(current_unit)
    std_u = _clean_unit(standard_unit)

    if in_u == std_u:
        return {
            "status": "success",
            "is_unit_matched": True,
            "nutrient_ko": nut.name_ko,
            "standard_value": round(float(current_value), 4),
            "standard_unit": standard_unit,
            "source": "단위 일치",
        }

    value = float(current_value)
    source = None
    if in_u == "iu" and code in _IU_CONVERSIONS:
        factor, cite = _IU_CONVERSIONS[code]
        value = value / factor
        source = cite
    elif in_u == "g" and "mg" in std_u:
        value, source = value * 1000.0, "질량 환산 1 g = 1000 mg"
    elif in_u == "mg" and "μg" in std_u:
        value, source = value * 1000.0, "질량 환산 1 mg = 1000 µg"
    elif in_u == "μg" and "mg" in std_u:
        value, source = value / 1000.0, "질량 환산 1000 µg = 1 mg"
    else:
        return {
            "status": "warning",
            "is_unit_matched": False,
            "message": f"'{current_unit}' → '{standard_unit}' 환산 규칙이 정의되지 "
            "않았습니다. 임의 환산하지 않습니다.",
            "nutrient_ko": nut.name_ko,
            "standard_unit": standard_unit,
        }

    return {
        "status": "success",
        "is_unit_matched": False,
        "nutrient_ko": nut.name_ko,
        "original_input": f"{current_value} {current_unit}",
        "standard_value": round(value, 4),
        "standard_unit": standard_unit,
        "source": source,
    }


if __name__ == "__main__":
    mcp.run()
