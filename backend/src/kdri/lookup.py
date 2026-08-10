from __future__ import annotations

from typing import Iterable, Optional

from kdri.models import Form, KdriRow, Limit, NutrientProfile


class BandNotFound(LookupError):
    """No KDRI band matches the requested nutrient, sex, and age."""


def find_band(
    bands: list[KdriRow], nutrient_code: str, sex: str, age: int
) -> KdriRow:
    for band in bands:
        if (
            band.nutrient_code == nutrient_code
            and band.gender == sex
            and band.age_min <= age <= band.age_max
        ):
            return band
    raise BandNotFound(f"no band for {nutrient_code} sex={sex} age={age}")


def _applies(limit: Limit, age: int, sex: str) -> bool:
    if not (limit.age_min <= age <= limit.age_max):
        return False
    return limit.sex in ("ALL", sex)


def resolve_limit(
    limits: list[Limit],
    band: KdriRow,
    nutrient_code: str,
    declared_forms: Iterable[Optional[str]],
    age: int,
    sex: str,
    ul_unit: str,
) -> Optional[Limit]:
    """Four-step resolution, most specific first (spec section 5.3)."""
    forms = [f for f in declared_forms if f]

    # 1. a limit written for one of the forms the user actually declared
    for form in forms:
        for limit in limits:
            if (
                limit.nutrient_code == nutrient_code
                and limit.applies_to_form == form
                and _applies(limit, age, sex)
            ):
                return limit

    # 2. a nutrient-wide limit covering all supplemental forms
    for limit in limits:
        if (
            limit.nutrient_code == nutrient_code
            and limit.applies_to_form is None
            and _applies(limit, age, sex)
        ):
            return limit

    # 3. the vendor band's own upper limit, which is always total-intake based
    if band.ul_limit is not None:
        return Limit(
            nutrient_code=nutrient_code,
            applies_to_form=None,
            age_min=band.age_min,
            age_max=band.age_max,
            sex=sex,
            value=band.ul_limit,
            unit=ul_unit,
            basis="total_intake",
            source="KDRI 2025 vendor table",
        )

    # 4. no established upper limit
    return None


def find_form(
    profile: Optional[NutrientProfile], form_ko: Optional[str]
) -> Optional[Form]:
    if profile is None or not form_ko:
        return None
    for form in profile.forms:
        if form.name_ko == form_ko:
            return form
    return None
