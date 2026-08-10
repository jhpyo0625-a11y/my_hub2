from __future__ import annotations

import math
from typing import Iterable, Optional

from kdri.lookup import BandNotFound, find_band, find_form, resolve_limit
from kdri.models import (
    KdriRow,
    Limit,
    NutrientProfile,
    NutrientResult,
    Profile,
    SupplementIntake,
    TraceStep,
)

MIN_ADULT_AGE = 19


def round_down(value: float, sig: int = 2) -> float:
    """Round toward zero to `sig` significant figures. Never rounds up."""
    if value <= 0:
        return 0.0
    magnitude = math.floor(math.log10(value)) - (sig - 1)
    step = 10.0**magnitude
    return math.floor(value / step) * step


def accumulate(
    profile: Optional[NutrientProfile], intakes: Iterable[SupplementIntake]
) -> tuple[float, float]:
    """Return (toward_target, toward_limit) — one pill can produce two numbers."""
    toward_target = 0.0
    toward_limit = 0.0
    for intake in intakes:
        form = find_form(profile, intake.form_ko)
        elemental = form.elemental_pct if form else 1.0
        target_factor = form.target_factor if form else 1.0
        ul_factor = form.ul_factor if form else 1.0
        base = intake.dose * elemental * intake.doses_per_day
        toward_target += base * target_factor
        toward_limit += base * ul_factor
    return toward_target, toward_limit


def compute_nutrient(
    nutrient_code: str,
    user: Profile,
    bands: list[KdriRow],
    limits: list[Limit],
    profiles: dict[str, NutrientProfile],
) -> NutrientResult:
    if user.age < MIN_ADULT_AGE:
        raise ValueError(f"age {user.age} is outside MVP scope (adults {MIN_ADULT_AGE}+)")

    trace: list[TraceStep] = []
    nutrient_profile = profiles.get(nutrient_code)
    intakes = [s for s in user.supplements if s.nutrient_code == nutrient_code]

    try:
        band = find_band(bands, nutrient_code, user.sex, user.age)
    except BandNotFound:
        return NutrientResult(
            nutrient_code=nutrient_code,
            status="UNKNOWN",
            target=None,
            from_diet=0.0,
            from_supplements=0.0,
            gap=0.0,
            headroom=None,
            recommend=0.0,
            trace=[TraceStep("band.missing", {"sex": user.sex, "age": user.age}, None)],
        )

    target = band.ri_base
    trace.append(
        TraceStep(
            "target.from_band",
            {"sex": user.sex, "age": user.age, "band": (band.age_min, band.age_max)},
            target,
            "KDRI 2025",
        )
    )

    toward_target, toward_limit = accumulate(nutrient_profile, intakes)
    trace.append(
        TraceStep(
            "intake.accumulated",
            {"items": len(intakes)},
            {"toward_target": toward_target, "toward_limit": toward_limit},
        )
    )

    ul_unit = nutrient_profile.ul_unit if nutrient_profile else band_unit_unknown()
    limit = resolve_limit(
        limits,
        band,
        nutrient_code,
        [s.form_ko for s in intakes],
        user.age,
        user.sex,
        ul_unit,
    )

    if limit is None:
        headroom = None
    elif limit.basis == "supplemental_only":
        headroom = limit.value - toward_limit
    else:
        headroom = None  # filled in below once diet is known

    baseline = nutrient_profile.diet_baseline_pct if nutrient_profile else None
    if baseline is None:
        trace.append(TraceStep("baseline.unknown", {"nutrient": nutrient_code}, None))
        return NutrientResult(
            nutrient_code=nutrient_code,
            status="UNKNOWN",
            target=target,
            from_diet=0.0,
            from_supplements=toward_target,
            gap=0.0,
            headroom=headroom,
            recommend=0.0,
            trace=trace,
        )

    from_diet = target * baseline
    trace.append(
        TraceStep(
            "diet.baseline",
            {"target": target, "pct": baseline},
            from_diet,
            nutrient_profile.diet_baseline_source,
        )
    )

    if limit is not None and limit.basis == "total_intake":
        headroom = limit.value - from_diet - toward_limit

    gap = max(0.0, target - from_diet - toward_target)
    recommend = gap if headroom is None else min(gap, headroom)
    recommend = round_down(max(0.0, recommend))

    if headroom is not None and headroom < 0:
        status = "OVER"
    elif gap > 0:
        status = "DEFICIT"
    else:
        status = "ADEQUATE"

    trace.append(
        TraceStep(
            "recommend.computed",
            {"gap": gap, "headroom": headroom, "basis": limit.basis if limit else None},
            recommend,
            limit.source if limit else None,
        )
    )

    return NutrientResult(
        nutrient_code=nutrient_code,
        status=status,
        target=target,
        from_diet=from_diet,
        from_supplements=toward_target,
        gap=gap,
        headroom=headroom,
        recommend=recommend,
        trace=trace,
    )


def band_unit_unknown() -> str:
    return "unknown"


# ── Task 11: full report with safety-first priority ordering ────────────

STATUS_RANK = {"OVER": 0, "DEFICIT": 1, "ADEQUATE": 2, "UNKNOWN": 3}


def _priority(result: NutrientResult) -> tuple[int, float]:
    rank = STATUS_RANK[result.status]
    if result.status == "DEFICIT" and result.target:
        # larger shortfall relative to target sorts earlier
        return (rank, -(result.gap / result.target))
    return (rank, 0.0)


def compute_report(
    user: Profile,
    bands: list[KdriRow],
    limits: list[Limit],
    profiles: dict[str, NutrientProfile],
) -> list[NutrientResult]:
    if user.age < MIN_ADULT_AGE:
        raise ValueError(f"age {user.age} is outside MVP scope (adults {MIN_ADULT_AGE}+)")

    codes = sorted({b.nutrient_code for b in bands})
    results = [
        compute_nutrient(code, user, bands, limits, profiles) for code in codes
    ]
    results.sort(key=_priority)
    for result in results:
        result.priority_score = float(STATUS_RANK[result.status])
    return results
