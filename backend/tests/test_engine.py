import dataclasses

import pytest

from kdri.engine import (
    accumulate,
    compute_nutrient,
    compute_report,
    evaluate_biomarkers,
    round_down,
)
from kdri.loader import load_bands, load_biomarker_refs, load_limits, load_profiles
from kdri.models import Biomarker, Profile, SupplementIntake


@pytest.fixture(scope="module")
def tables():
    return load_bands(), load_limits(), load_profiles()


def pin_baselines(profiles, **baselines):
    """Curated baselines are null until KNHANES-sourced; pin them for a test
    that exercises a diet-dependent path, mirroring the golden/property tests."""
    out = dict(profiles)
    for code, pct in baselines.items():
        out[code] = dataclasses.replace(out[code], diet_baseline_pct=pct)
    return out


# ── Task 8: accounting + core computation ───────────────────────────────


def test_round_down_never_rounds_up():
    assert round_down(57.6) == 57.0
    assert round_down(293.6) == 290.0
    assert round_down(0.0) == 0.0
    assert round_down(-5.0) == 0.0


def test_accumulate_applies_elemental_percentage(tables):
    _, _, profiles = tables
    intakes = [SupplementIntake("magnesium", dose=400, form_ko="마그네슘 비스글리시네이트")]
    toward_target, toward_limit = accumulate(profiles["magnesium"], intakes)
    assert toward_target == pytest.approx(56.4)
    assert toward_limit == pytest.approx(56.4)


def test_accumulate_splits_target_and_limit_for_folate(tables):
    _, _, profiles = tables
    intakes = [SupplementIntake("folate", dose=200, form_ko="엽산")]
    toward_target, toward_limit = accumulate(profiles["folate"], intakes)
    assert toward_target == pytest.approx(340.0)
    assert toward_limit == pytest.approx(200.0)


def test_accumulate_multiplies_by_doses_per_day(tables):
    _, _, profiles = tables
    intakes = [SupplementIntake("magnesium", dose=200, doses_per_day=2, form_ko="산화마그네슘")]
    toward_target, _ = accumulate(profiles["magnesium"], intakes)
    assert toward_target == pytest.approx(241.2)


def test_unknown_form_is_treated_as_elemental(tables):
    _, _, profiles = tables
    intakes = [SupplementIntake("magnesium", dose=100, form_ko=None)]
    toward_target, _ = accumulate(profiles["magnesium"], intakes)
    assert toward_target == pytest.approx(100.0)


def test_missing_diet_baseline_yields_unknown(tables):
    bands, limits, profiles = tables
    profile = Profile(age=34, sex="M")
    result = compute_nutrient("zinc", profile, bands, limits, profiles)
    assert result.status == "UNKNOWN"
    assert result.recommend == 0.0


def test_over_supplemental_limit_surfaces_even_without_a_baseline(tables):
    """Safety-first: 600mg MgO is over the 350mg supplemental limit and must
    report OVER, not UNKNOWN, even though magnesium's diet baseline is null."""
    bands, limits, profiles = tables
    assert profiles["magnesium"].diet_baseline_pct is None  # honest curated state
    user = Profile(
        age=34,
        sex="M",
        supplements=(SupplementIntake("magnesium", dose=600, form_ko="산화마그네슘"),),
    )
    result = compute_nutrient("magnesium", user, bands, limits, profiles)
    assert result.status == "OVER"
    assert result.headroom == pytest.approx(-11.8)
    assert result.recommend == 0.0
    assert any(s.rule_id == "recommend.computed" for s in result.trace)


def test_total_intake_limit_subtracts_diet(tables):
    """Iron's limit comes from the vendor band, so it is total-intake based."""
    bands, limits, profiles = tables
    profiles = pin_baselines(profiles, iron=0.60)
    profile = Profile(age=34, sex="F")
    result = compute_nutrient("iron", profile, bands, limits, profiles)
    # F 30-49 iron: RI 12, UL 45, baseline 0.60 -> diet 7.2
    assert result.target == 12.0
    assert result.from_diet == pytest.approx(7.2)
    assert result.headroom == pytest.approx(45.0 - 7.2)
    assert result.recommend <= result.gap + 1e-9


# ── Task 11: full report + ordering ─────────────────────────────────────


def test_report_covers_every_in_scope_nutrient(tables):
    bands, limits, profiles = tables
    results = compute_report(Profile(age=34, sex="F"), bands, limits, profiles)
    assert len(results) == 30
    assert len({r.nutrient_code for r in results}) == 30


def test_report_puts_over_first(tables):
    bands, limits, profiles = tables
    profiles = pin_baselines(profiles, magnesium=0.70)
    user = Profile(
        age=34,
        sex="M",
        supplements=(SupplementIntake("magnesium", dose=600, form_ko="산화마그네슘"),),
    )
    results = compute_report(user, bands, limits, profiles)
    assert results[0].nutrient_code == "magnesium"
    assert results[0].status == "OVER"


def test_report_orders_unknown_last(tables):
    bands, limits, profiles = tables
    results = compute_report(Profile(age=34, sex="F"), bands, limits, profiles)
    statuses = [r.status for r in results]
    unknown_positions = [i for i, s in enumerate(statuses) if s == "UNKNOWN"]
    known_positions = [i for i, s in enumerate(statuses) if s != "UNKNOWN"]
    if unknown_positions and known_positions:
        assert min(unknown_positions) > max(known_positions)


def test_under_19_is_refused(tables):
    bands, limits, profiles = tables
    with pytest.raises(ValueError, match="outside MVP scope"):
        compute_report(Profile(age=17, sex="F"), bands, limits, profiles)


# ── Task 12: trace completeness ─────────────────────────────────────────


def test_every_computed_result_carries_a_trace(tables):
    bands, limits, profiles = tables
    user = Profile(
        age=34,
        sex="M",
        supplements=(SupplementIntake("magnesium", dose=400, form_ko="산화마그네슘"),),
    )
    for result in compute_report(user, bands, limits, profiles):
        assert result.trace, f"{result.nutrient_code} has no trace"


def test_recommendation_is_always_traceable(tables):
    bands, limits, profiles = tables
    user = Profile(age=34, sex="M")
    for result in compute_report(user, bands, limits, profiles):
        if result.recommend > 0:
            rules = {step.rule_id for step in result.trace}
            assert "recommend.computed" in rules
            assert "target.from_band" in rules
            assert "diet.baseline" in rules


# ── FR-13: biomarker-driven priority ────────────────────────────────────


@pytest.fixture(scope="module")
def bmrefs():
    return load_biomarker_refs()


def test_biomarker_low_hemoglobin_is_sex_specific(bmrefs):
    """WHO anaemia bound: M <13, F <12 g/dL. 12.5 flags a man, not a woman."""
    male = Profile(age=34, sex="M", biomarkers=(Biomarker("hemoglobin", 12.5, "g/dL"),))
    female = Profile(age=34, sex="F", biomarkers=(Biomarker("hemoglobin", 12.5, "g/dL"),))
    assert "iron" in evaluate_biomarkers(male, bmrefs)
    assert "iron" not in evaluate_biomarkers(female, bmrefs)


def test_biomarker_in_range_does_not_flag(bmrefs):
    ok = Profile(age=34, sex="F", biomarkers=(Biomarker("hemoglobin", 13.5, "g/dL"),))
    assert evaluate_biomarkers(ok, bmrefs) == {}


def test_biomarker_flag_prioritizes_iron_without_changing_numbers(tables, bmrefs):
    """Low hemoglobin lifts iron to the top (after any OVER) but must not move
    a single dosing number — decision 10, 'prioritize, never re-target'."""
    bands, limits, profiles = tables
    profiles = pin_baselines(profiles, iron=0.60)
    base = Profile(age=34, sex="F")
    flagged = Profile(age=34, sex="F", biomarkers=(Biomarker("hemoglobin", 10.5, "g/dL"),))

    def iron_of(user, refs):
        return [r for r in compute_report(user, bands, limits, profiles, refs)
                if r.nutrient_code == "iron"][0]

    a = iron_of(base, [])
    b = iron_of(flagged, bmrefs)
    # numbers identical
    assert (a.target, a.from_diet, a.gap, a.recommend, a.status) == (
        b.target, b.from_diet, b.gap, b.recommend, b.status
    )
    # but flagged, and now first (no OVER present)
    assert a.biomarker_flag is None
    assert b.biomarker_flag is not None and b.biomarker_flag.direction == "low"
    ranked = compute_report(flagged, bands, limits, profiles, bmrefs)
    assert ranked[0].nutrient_code == "iron"


def test_over_still_outranks_a_biomarker_flag(tables, bmrefs):
    """Safety first: an OVER nutrient leads even when a biomarker is flagged."""
    bands, limits, profiles = tables
    profiles = pin_baselines(profiles, magnesium=0.70, iron=0.60)
    user = Profile(
        age=34,
        sex="F",
        supplements=(SupplementIntake("magnesium", dose=600, form_ko="산화마그네슘"),),
        biomarkers=(Biomarker("hemoglobin", 10.5, "g/dL"),),
    )
    ranked = compute_report(user, bands, limits, profiles, bmrefs)
    assert ranked[0].nutrient_code == "magnesium" and ranked[0].status == "OVER"
    assert ranked[1].nutrient_code == "iron" and ranked[1].biomarker_flag is not None


def test_trace_records_the_limit_source_when_one_applies(tables):
    bands, limits, profiles = tables
    profiles = pin_baselines(profiles, magnesium=0.70)
    user = Profile(age=34, sex="M")
    result = compute_nutrient("magnesium", user, bands, limits, profiles)
    step = [s for s in result.trace if s.rule_id == "recommend.computed"][0]
    assert step.citation and "상한섭취량" in step.citation
