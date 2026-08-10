from pathlib import Path

from kdri.loader import apply_overrides, check_published_ranges, load_kdri_rows, load_nutrients

FIXTURE = Path(__file__).parent / "fixtures" / "kdri_2025_ranges.csv"


def test_vendor_data_matches_published_2025_ranges():
    rows = apply_overrides(load_kdri_rows())
    deviations = check_published_ranges(rows, load_nutrients(), FIXTURE)
    assert deviations == [], "\n".join(deviations)


def test_range_check_catches_a_reintroduced_stale_value():
    """Without the override, magnesium's 2020 value of 410 must be reported."""
    rows = load_kdri_rows()  # deliberately unpatched
    deviations = check_published_ranges(rows, load_nutrients(), FIXTURE)
    assert any("magnesium" in d for d in deviations)
