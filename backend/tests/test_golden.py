"""The five worked examples from spec section 6.7.

Each asserts a number that a naive implementation gets wrong without crashing.
Profiles are built in-test so provisional diet baselines can change freely.
"""

import dataclasses

import pytest

from kdri.engine import compute_nutrient
from kdri.loader import load_bands, load_limits, load_profiles
from kdri.lookup import find_band
from kdri.models import Profile, SupplementIntake


@pytest.fixture(scope="module")
def bands():
    return load_bands()


@pytest.fixture(scope="module")
def limits():
    return load_limits()


def profiles_with(code: str, baseline: float):
    """Curated profiles with one nutrient's diet baseline pinned for the test."""
    loaded = load_profiles()
    loaded[code] = dataclasses.replace(loaded[code], diet_baseline_pct=baseline)
    return loaded


def test_a_magnesium_bisglycinate_elemental_conversion(bands, limits):
    """400 mg of bisglycinate is 56.4 mg elemental, not 400."""
    user = Profile(
        age=34,
        sex="M",
        supplements=(SupplementIntake("magnesium", dose=400, form_ko="마그네슘 비스글리시네이트"),),
    )
    result = compute_nutrient("magnesium", user, bands, limits, profiles_with("magnesium", 0.70))

    assert result.target == 380.0
    assert result.from_diet == pytest.approx(266.0)
    assert result.from_supplements == pytest.approx(56.4)
    assert result.gap == pytest.approx(57.6)
    assert result.headroom == pytest.approx(293.6)
    assert result.recommend == 57.0
    assert result.status == "DEFICIT"


def test_b_magnesium_oxide_600_is_over_the_supplemental_limit(bands, limits):
    """600 mg MgO is 361.8 mg elemental, past the 350 mg supplemental limit."""
    user = Profile(
        age=34,
        sex="M",
        supplements=(SupplementIntake("magnesium", dose=600, form_ko="산화마그네슘"),),
    )
    result = compute_nutrient("magnesium", user, bands, limits, profiles_with("magnesium", 0.70))

    assert result.from_supplements == pytest.approx(361.8)
    assert result.headroom == pytest.approx(-11.8)
    assert result.status == "OVER"
    assert result.recommend == 0.0


def test_b2_magnesium_limit_ignores_diet(bands, limits):
    """The supplemental-only basis must exclude diet, or RI 380 > UL 350 breaks."""
    user = Profile(age=34, sex="M")
    result = compute_nutrient("magnesium", user, bands, limits, profiles_with("magnesium", 0.70))
    assert result.headroom == pytest.approx(350.0)
    assert result.status == "DEFICIT"


def test_c_sex_is_required_and_changes_the_target(bands):
    """Iron F 30-49 is 12 mg, M is 8 mg, and no ALL band exists for adults."""
    assert find_band(bands, "iron", "F", 34).ri_base == 12.0
    assert find_band(bands, "iron", "M", 34).ri_base == 8.0
    assert not any(b.gender == "ALL" for b in bands)


def test_d_nicotinamide_resolves_to_its_own_limit(bands, limits):
    """500 mg nicotinamide is inside its 850 limit."""
    user = Profile(
        age=34,
        sex="M",
        supplements=(SupplementIntake("niacin", dose=500, form_ko="니코틴아미드"),),
    )
    result = compute_nutrient("niacin", user, bands, limits, profiles_with("niacin", 0.90))

    assert result.headroom == pytest.approx(350.0)
    assert result.status == "ADEQUATE"
    assert result.recommend == 0.0


def test_d2_nicotinic_acid_resolves_to_the_stricter_limit(bands, limits):
    """The same dose as nicotinic acid is far past its 35 mg limit."""
    user = Profile(
        age=34,
        sex="M",
        supplements=(SupplementIntake("niacin", dose=500, form_ko="니코틴산"),),
    )
    result = compute_nutrient("niacin", user, bands, limits, profiles_with("niacin", 0.90))
    assert result.status == "OVER"


def test_e_folate_dfe_conversion_flips_the_answer(bands, limits):
    """200 ug folic acid is 340 ug DFE toward target but 200 ug toward the limit."""
    user = Profile(
        age=34,
        sex="F",
        supplements=(SupplementIntake("folate", dose=200, form_ko="엽산"),),
    )
    result = compute_nutrient("folate", user, bands, limits, profiles_with("folate", 0.40))

    assert result.target == 400.0
    assert result.from_diet == pytest.approx(160.0)
    assert result.from_supplements == pytest.approx(340.0)
    assert result.gap == 0.0
    assert result.headroom == pytest.approx(800.0)
    assert result.status == "ADEQUATE"
