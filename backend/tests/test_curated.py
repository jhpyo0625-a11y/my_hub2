import pytest

from kdri.loader import (
    in_scope_codes,
    load_biomarker_refs,
    load_energy_ratios,
    load_interactions,
    load_limits,
    load_nutrients,
    load_profiles,
)


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


# ── Task 13: complete, cited profiles for all 30 ────────────────────────


def test_every_in_scope_nutrient_has_a_profile():
    profiles = load_profiles()
    missing = in_scope_codes(load_nutrients()) - set(profiles)
    assert missing == set(), f"missing profiles: {sorted(missing)}"


def test_every_baseline_is_sourced_or_explicitly_absent():
    for profile in load_profiles().values():
        if profile.diet_baseline_pct is None:
            assert profile.diet_baseline_source == "none"
        else:
            assert profile.diet_baseline_source
            assert "PROVISIONAL" not in profile.diet_baseline_source
            assert 0.0 <= profile.diet_baseline_pct <= 1.5


def test_every_form_is_cited():
    for profile in load_profiles().values():
        for form in profile.forms:
            assert form.source.strip(), f"{profile.nutrient_code}/{form.name_ko} uncited"
            assert 0.0 < form.elemental_pct <= 1.0


# ── Task 14: interactions + AMDR reference ──────────────────────────────


def test_interactions_are_cited_and_scoped():
    rows = load_interactions()
    assert rows
    codes = in_scope_codes(load_nutrients())
    for row in rows:
        assert row["nutrient_code"] in codes
        assert row["severity"] in ("low", "medium", "high", "critical")
        assert row["source"].strip()
        assert "가이드" != row["source"].strip(), "name a specific reference"


def test_amdr_matches_the_2025_revision():
    ratios = {r["macronutrient"]: r for r in load_energy_ratios()}
    assert (float(ratios["carbohydrate"]["pct_min"]), float(ratios["carbohydrate"]["pct_max"])) == (50.0, 65.0)
    assert (float(ratios["protein"]["pct_min"]), float(ratios["protein"]["pct_max"])) == (10.0, 20.0)
    assert (float(ratios["fat"]["pct_min"]), float(ratios["fat"]["pct_max"])) == (15.0, 30.0)


def test_engine_never_imports_energy_ratios():
    """AMDR is reference-only; the engine has no denominator to compute it."""
    source = (__import__("pathlib").Path(__file__).parents[1] / "src" / "kdri" / "engine.py").read_text(encoding="utf-8")
    assert "energy_ratio" not in source


def test_guidance_is_cited_and_populated_where_present():
    """Block-3 form/timing advice is optional per nutrient, but any block that
    exists must carry a source (loader raises otherwise) and say something."""
    profiles = load_profiles()
    assert profiles["magnesium"].guidance is not None
    assert profiles["iron"].guidance is not None
    for code, prof in profiles.items():
        g = prof.guidance
        if g is not None:
            assert g.source.strip(), f"{code} guidance uncited"
            assert g.recommended_form_ko or g.form_reason_ko or g.timing_ko, (
                f"{code} guidance is empty"
            )


def test_biomarker_refs_are_cited_scoped_and_bounded():
    refs = load_biomarker_refs()
    assert refs
    codes = in_scope_codes(load_nutrients())
    for ref in refs:
        assert ref.nutrient_code in codes
        assert ref.sex in ("M", "F", "ALL")
        assert ref.low is not None or ref.high is not None
        assert ref.source.strip()
        assert ref.unit.strip()
