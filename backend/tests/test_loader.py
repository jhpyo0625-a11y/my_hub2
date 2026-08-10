import csv

import pytest

from kdri import VENDOR_DIR
from kdri.loader import (
    apply_overrides,
    filter_to_mvp_scope,
    in_scope_codes,
    load_bands,
    load_kdri_rows,
    load_nutrients,
)


def test_vendor_files_present_with_expected_row_counts():
    codes = list(csv.DictReader((VENDOR_DIR / "nutrient_codes.csv").open(encoding="utf-8")))
    bands = list(csv.DictReader((VENDOR_DIR / "kdri_standards.csv").open(encoding="utf-8")))
    assert len(codes) == 47
    assert len(bands) == 1052
    assert (VENDOR_DIR / "2025_KDRI_보도자료.pdf").exists()


# ── Task 2 ──────────────────────────────────────────────────────────────


def test_load_nutrients_parses_flags_and_synonyms():
    nutrients = load_nutrients()
    assert len(nutrients) == 47
    mg = nutrients["magnesium"]
    assert mg.name_ko == "마그네슘"
    assert mg.group == "mineral"
    assert mg.has_rni is True
    assert mg.has_ul is True
    assert "산화마그네슘" in mg.synonyms

    biotin = nutrients["biotin"]
    assert biotin.has_rni is False
    assert biotin.has_ai is True


def test_load_kdri_rows_parses_blanks_as_none():
    rows = load_kdri_rows()
    assert len(rows) == 1052
    mg_adult = [
        r for r in rows
        if r.nutrient_code == "magnesium" and r.gender == "M" and (r.age_min, r.age_max) == (30, 49)
    ]
    assert len(mg_adult) == 1
    assert mg_adult[0].ri_base == 380.0
    assert mg_adult[0].ul_limit is None


# ── Task 3 ──────────────────────────────────────────────────────────────


def test_apply_overrides_corrects_stale_magnesium_value():
    rows = load_kdri_rows()
    before = [
        r for r in rows
        if r.nutrient_code == "magnesium" and r.gender == "M" and (r.age_min, r.age_max) == (15, 18)
    ][0]
    assert before.ri_base == 410.0

    patched = apply_overrides(rows)
    after = [
        r for r in patched
        if r.nutrient_code == "magnesium" and r.gender == "M" and (r.age_min, r.age_max) == (15, 18)
    ][0]
    assert after.ri_base == 380.0
    assert len(patched) == len(rows)


def test_apply_overrides_rejects_uncited_rows(tmp_path):
    (tmp_path / "overrides.csv").write_text(
        "nutrient_code,gender,age_min,age_max,field,value,source,note\n"
        "magnesium,M,15,18,ri_base,380,,\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="source"):
        apply_overrides(load_kdri_rows(), curated_dir=tmp_path)


# ── Task 5 ──────────────────────────────────────────────────────────────


def test_in_scope_is_thirty_nutrients():
    codes = in_scope_codes(load_nutrients())
    assert len(codes) == 30
    assert "epa_dha" in codes
    assert "magnesium" in codes
    assert "leucine" not in codes
    assert "energy" not in codes


def test_filter_yields_exactly_300_rectangular_rows():
    rows = filter_to_mvp_scope(apply_overrides(load_kdri_rows()), load_nutrients())
    assert len(rows) == 300
    assert {r.gender for r in rows} == {"M", "F"}
    assert all(r.age_min >= 19 for r in rows)
    assert all(r.ri_base is not None for r in rows)
    assert not any((r.age_min, r.age_max) == (0, 99) for r in rows)
    keys = {(r.nutrient_code, r.gender, r.age_min, r.age_max) for r in rows}
    assert len(keys) == 300


def test_load_bands_runs_the_full_pipeline():
    assert len(load_bands()) == 300
