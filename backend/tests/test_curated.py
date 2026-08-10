import pytest

from kdri.loader import load_limits, load_profiles


def test_limits_load_with_form_scoping():
    limits = load_limits()
    niacin = [l for l in limits if l.nutrient_code == "niacin"]
    assert {l.applies_to_form for l in niacin} == {"니코틴산", "니코틴아미드"}
    assert [l.value for l in niacin if l.applies_to_form == "니코틴아미드"] == [850.0]

    magnesium = [l for l in limits if l.nutrient_code == "magnesium"]
    assert len(magnesium) == 1
    assert magnesium[0].applies_to_form is None
    assert magnesium[0].basis == "supplemental_only"


def test_every_limit_row_is_cited_and_complete():
    for limit in load_limits():
        assert limit.source.strip(), f"{limit.nutrient_code} limit has no source"
        assert limit.unit.strip()
        assert limit.basis in ("total_intake", "supplemental_only")


def test_folate_declares_split_units_and_conversion():
    folate = load_profiles()["folate"]
    assert folate.target_unit == "µg DFE"
    assert folate.ul_unit == "µg"
    synthetic = [f for f in folate.forms if f.name_ko == "엽산"][0]
    assert synthetic.target_factor == 1.7
    assert synthetic.ul_factor == 1.0


def test_forms_default_conversion_factors_to_one():
    mgo = [f for f in load_profiles()["magnesium"].forms if f.name_ko == "산화마그네슘"][0]
    assert mgo.target_factor == 1.0
    assert mgo.ul_factor == 1.0
    assert mgo.elemental_pct == pytest.approx(0.603)


def test_split_unit_nutrients_require_conversion_factors_on_every_form():
    for profile in load_profiles().values():
        if profile.target_unit != profile.ul_unit:
            for form in profile.forms:
                assert form.target_factor is not None
                assert form.ul_factor is not None
