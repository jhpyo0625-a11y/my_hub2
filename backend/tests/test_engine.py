import pytest

from kdri.engine import accumulate, compute_nutrient, compute_report, round_down
from kdri.loader import load_bands, load_limits, load_profiles
from kdri.models import Profile, SupplementIntake


@pytest.fixture(scope="module")
def tables():
    return load_bands(), load_limits(), load_profiles()


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


def test_total_intake_limit_subtracts_diet(tables):
    """Iron's limit comes from the vendor band, so it is total-intake based."""
    bands, limits, profiles = tables
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


def test_trace_records_the_limit_source_when_one_applies(tables):
    bands, limits, profiles = tables
    user = Profile(age=34, sex="M")
    result = compute_nutrient("magnesium", user, bands, limits, profiles)
    step = [s for s in result.trace if s.rule_id == "recommend.computed"][0]
    assert step.citation and "상한섭취량" in step.citation
