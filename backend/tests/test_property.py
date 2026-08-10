"""Exhaustive invariant check across all 300 adult band rows.

The engine must never recommend a dose that pushes intake past an upper limit,
for any nutrient, band, sex, or starting intake level.
"""

import dataclasses

import pytest

from kdri.engine import compute_nutrient, round_down
from kdri.loader import load_bands, load_limits, load_profiles
from kdri.models import NutrientProfile, Profile, SupplementIntake

BAND_MIDPOINTS = {(19, 29): 25, (30, 49): 40, (50, 64): 57, (65, 74): 70, (75, 99): 80}
INTAKE_FRACTIONS = (0.0, 0.5, 1.0, 5.0)
TOLERANCE = 1e-9


@pytest.fixture(scope="module")
def tables():
    return load_bands(), load_limits()


def baseline_profiles(bands) -> dict[str, NutrientProfile]:
    """A 0.5 diet baseline for every in-scope nutrient, forms preserved."""
    curated = load_profiles()
    out: dict[str, NutrientProfile] = {}
    for code in {b.nutrient_code for b in bands}:
        existing = curated.get(code)
        if existing is not None:
            out[code] = dataclasses.replace(existing, diet_baseline_pct=0.5)
        else:
            out[code] = NutrientProfile(
                nutrient_code=code,
                target_unit="unit",
                ul_unit="unit",
                diet_baseline_pct=0.5,
                diet_baseline_source="TEST",
            )
    return out


def test_every_adult_band_respects_its_upper_limit(tables):
    bands, limits = tables
    profiles = baseline_profiles(bands)
    assert len(bands) == 300

    checked = 0
    for band in bands:
        age = BAND_MIDPOINTS[(band.age_min, band.age_max)]
        for fraction in INTAKE_FRACTIONS:
            dose = (band.ri_base or 0.0) * fraction
            user = Profile(
                age=age,
                sex=band.gender,
                supplements=(
                    (SupplementIntake(band.nutrient_code, dose=dose),) if dose else ()
                ),
            )
            result = compute_nutrient(
                band.nutrient_code, user, bands, limits, profiles
            )
            checked += 1

            assert result.recommend >= 0.0, result
            assert result.recommend <= result.gap + TOLERANCE, result
            if result.headroom is not None:
                assert result.recommend <= max(0.0, result.headroom) + TOLERANCE, result
            else:
                assert result.recommend == round_down(result.gap), result

    assert checked == 300 * len(INTAKE_FRACTIONS)


def test_recommendation_never_pushes_total_past_the_limit(tables):
    bands, limits = tables
    profiles = baseline_profiles(bands)

    for band in bands:
        age = BAND_MIDPOINTS[(band.age_min, band.age_max)]
        user = Profile(age=age, sex=band.gender)
        result = compute_nutrient(band.nutrient_code, user, bands, limits, profiles)
        if result.headroom is None or result.status == "OVER":
            continue
        consumed = result.from_supplements
        if result.headroom is not None:
            assert consumed + result.recommend <= (
                result.from_supplements + result.headroom + TOLERANCE
            ), result
