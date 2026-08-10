from __future__ import annotations

import math
from typing import Iterable, Optional

from kdri.lookup import BandNotFound, find_band, find_form, resolve_limit
from kdri.models import (
    BiomarkerFlag,
    BiomarkerRef,
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
        # Safety-first: a confirmed overshoot of a supplemental-only limit is
        # OVER even without a diet baseline. That basis excludes food, so diet
        # is not part of the comparison — the overdose is real either way, and
        # "OVER leads" outranks "no baseline -> UNKNOWN" (spec section 6.4).
        if (
            limit is not None
            and limit.basis == "supplemental_only"
            and headroom is not None
            and headroom < 0
        ):
            trace.append(
                TraceStep(
                    "recommend.computed",
                    {"gap": None, "headroom": headroom, "basis": limit.basis},
                    0.0,
                    limit.source,
                )
            )
            return NutrientResult(
                nutrient_code=nutrient_code,
                status="OVER",
                target=target,
                from_diet=0.0,
                from_supplements=toward_target,
                gap=0.0,
                headroom=headroom,
                recommend=0.0,
                trace=trace,
            )
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

def evaluate_biomarkers(
    user: Profile, refs: list[BiomarkerRef]
) -> dict[str, BiomarkerFlag]:
    """Map each out-of-range biomarker to the nutrient it flags.

    A value below its cited `low` reference bound flags the nutrient. This
    prioritizes and contextualizes only — it never enters any dose arithmetic.
    Sex-specific bounds match the user's sex or an 'ALL' row. First matching
    ref per nutrient wins.
    """
    flags: dict[str, BiomarkerFlag] = {}
    for bm in user.biomarkers:
        if bm.value is None:
            continue
        for ref in refs:
            if ref.biomarker_code != bm.code or ref.sex not in ("ALL", user.sex):
                continue
            if ref.low is not None and bm.value < ref.low:
                flags.setdefault(
                    ref.nutrient_code,
                    BiomarkerFlag(
                        biomarker_code=bm.code,
                        nutrient_code=ref.nutrient_code,
                        value=bm.value,
                        unit=bm.unit or ref.unit,
                        threshold=ref.low,
                        direction="low",
                        source=ref.source,
                    ),
                )
    return flags


# Priority tiers, safety-first (spec section 6.5). A biomarker-flagged nutrient
# sits directly under OVER and above every unflagged nutrient — so a low
# hemoglobin surfaces iron even when its dose is DEFICIT or UNKNOWN.
def _tier(result: NutrientResult) -> int:
    if result.status == "OVER":
        return 0
    if result.biomarker_flag is not None:
        return 1
    if result.status == "DEFICIT":
        return 2
    if result.status == "ADEQUATE":
        return 3
    return 4  # UNKNOWN


def _priority(result: NutrientResult) -> tuple[int, float]:
    ratio = (
        -(result.gap / result.target)
        if (result.status == "DEFICIT" and result.target)
        else 0.0
    )
    return (_tier(result), ratio)


def compute_report(
    user: Profile,
    bands: list[KdriRow],
    limits: list[Limit],
    profiles: dict[str, NutrientProfile],
    biomarker_refs: list[BiomarkerRef] = (),
) -> list[NutrientResult]:
    if user.age < MIN_ADULT_AGE:
        raise ValueError(f"age {user.age} is outside MVP scope (adults {MIN_ADULT_AGE}+)")

    codes = sorted({b.nutrient_code for b in bands})
    results = [
        compute_nutrient(code, user, bands, limits, profiles) for code in codes
    ]

    flags = evaluate_biomarkers(user, list(biomarker_refs))
    for result in results:
        flag = flags.get(result.nutrient_code)
        if flag is not None:
            result.biomarker_flag = flag
            result.trace.append(
                TraceStep(
                    "biomarker.flag",
                    {
                        "biomarker": flag.biomarker_code,
                        "value": flag.value,
                        "threshold": flag.threshold,
                        "direction": flag.direction,
                    },
                    "prioritized",  # note: no dose number changes
                    flag.source,
                )
            )

    results.sort(key=_priority)
    for result in results:
        result.priority_score = float(_tier(result))
    return results
