import pytest

from kdri.loader import load_bands, load_limits, load_profiles
from kdri.lookup import BandNotFound, find_band, find_form, resolve_limit


@pytest.fixture(scope="module")
def bands():
    return load_bands()


@pytest.fixture(scope="module")
def limits():
    return load_limits()


def test_find_band_is_sex_specific(bands):
    female = find_band(bands, "iron", "F", 34)
    male = find_band(bands, "iron", "M", 34)
    assert female.ri_base == 12.0
    assert male.ri_base == 8.0


def test_find_band_rejects_out_of_scope_age(bands):
    with pytest.raises(BandNotFound):
        find_band(bands, "iron", "F", 17)


def test_resolve_limit_prefers_the_declared_form(bands, limits):
    band = find_band(bands, "niacin", "M", 34)
    limit = resolve_limit(limits, band, "niacin", ["니코틴아미드"], 34, "M", "mg NE")
    assert limit.value == 850.0
    assert limit.basis == "supplemental_only"


def test_resolve_limit_picks_the_other_niacin_form(bands, limits):
    band = find_band(bands, "niacin", "M", 34)
    limit = resolve_limit(limits, band, "niacin", ["니코틴산"], 34, "M", "mg NE")
    assert limit.value == 35.0


def test_resolve_limit_falls_back_to_nutrient_wide_row(bands, limits):
    band = find_band(bands, "magnesium", "M", 34)
    limit = resolve_limit(limits, band, "magnesium", [], 34, "M", "mg")
    assert limit.value == 350.0
    assert limit.applies_to_form is None


def test_resolve_limit_falls_back_to_vendor_band(bands, limits):
    band = find_band(bands, "zinc", "F", 34)
    limit = resolve_limit(limits, band, "zinc", [], 34, "F", "mg")
    assert limit.value == 35.0
    assert limit.basis == "total_intake"


def test_resolve_limit_returns_none_when_no_limit_exists(bands, limits):
    band = find_band(bands, "biotin", "F", 34)
    assert resolve_limit(limits, band, "biotin", [], 34, "F", "µg") is None


def test_find_form_matches_by_korean_name():
    profile = load_profiles()["magnesium"]
    assert find_form(profile, "산화마그네슘").elemental_pct == pytest.approx(0.603)
    assert find_form(profile, "없는형태") is None
    assert find_form(profile, None) is None
