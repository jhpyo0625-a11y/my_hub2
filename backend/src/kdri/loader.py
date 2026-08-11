from __future__ import annotations

import csv
import dataclasses
from pathlib import Path
from typing import Optional

import yaml

from kdri import CURATED_DIR, VENDOR_DIR
from kdri.models import (
    BiomarkerRef,
    Form,
    Guidance,
    KdriRow,
    Limit,
    Nutrient,
    NutrientProfile,
)


def _opt_float(raw: str) -> Optional[float]:
    raw = (raw or "").strip()
    return float(raw) if raw else None


# ── Task 2: vendor loading ──────────────────────────────────────────────


def load_nutrients(vendor_dir: Path = VENDOR_DIR) -> dict[str, Nutrient]:
    path = vendor_dir / "nutrient_codes.csv"
    out: dict[str, Nutrient] = {}
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            synonyms = tuple(s for s in (row["synonyms_ko_label"] or "").split("|") if s)
            out[row["nutrient_code"]] = Nutrient(
                code=row["nutrient_code"],
                name_ko=row["nutrient_ko"],
                group=row["group_name"],
                kdri_unit=row["kdri_unit"],
                synonyms=synonyms,
                has_rni=row["has_rni"] == "true",
                has_ai=row["has_ai"] == "true",
                has_ul=row["has_ul"] == "true",
            )
    return out


def load_kdri_rows(vendor_dir: Path = VENDOR_DIR) -> list[KdriRow]:
    path = vendor_dir / "kdri_standards.csv"
    with path.open(encoding="utf-8") as fh:
        return [
            KdriRow(
                nutrient_code=row["nutrient_code"],
                age_min=int(row["age_min"]),
                age_max=int(row["age_max"]),
                gender=row["gender"],
                ri_base=_opt_float(row["ri_base"]),
                ul_limit=_opt_float(row["ul_limit"]),
            )
            for row in csv.DictReader(fh)
        ]


# ── Task 3: cited vendor value overrides ────────────────────────────────


def apply_overrides(
    rows: list[KdriRow], curated_dir: Path = CURATED_DIR
) -> list[KdriRow]:
    path = curated_dir / "overrides.csv"
    if not path.exists():
        return list(rows)

    patches: list[dict[str, str]] = []
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if not (row.get("source") or "").strip():
                raise ValueError(
                    f"overrides.csv row for {row['nutrient_code']} has no source; "
                    "every deviation from vendor data must be cited"
                )
            patches.append(row)

    out = list(rows)
    for patch in patches:
        matched = False
        for i, row in enumerate(out):
            if (
                row.nutrient_code == patch["nutrient_code"]
                and row.gender == patch["gender"]
                and row.age_min == int(patch["age_min"])
                and row.age_max == int(patch["age_max"])
            ):
                out[i] = dataclasses.replace(
                    row, **{patch["field"]: float(patch["value"])}
                )
                matched = True
        if not matched:
            raise ValueError(f"overrides.csv row matched no vendor row: {patch}")
    return out


# ── Task 4: 2025 published-range validation ─────────────────────────────

INFANT_BANDS = {(0, 5), (6, 11)}
PREGNANCY_BAND = (0, 99)
TOLERANCE = 1e-9


def check_published_ranges(
    rows: list[KdriRow],
    nutrients: dict[str, Nutrient],
    fixture_path: Path,
) -> list[str]:
    """Compare each nutrient's RI/AI range against the published 2025 range.

    Returns a list of human-readable deviations; empty means clean.
    """
    deviations: list[str] = []
    with fixture_path.open(encoding="utf-8") as fh:
        expectations = list(csv.DictReader(fh))

    for exp in expectations:
        code = exp["nutrient_code"]
        if exp["allowlisted"] == "true":
            continue

        nutrient = nutrients[code]
        excluded = {PREGNANCY_BAND}
        if nutrient.has_rni:
            excluded |= INFANT_BANDS

        values = [
            r.ri_base
            for r in rows
            if r.nutrient_code == code
            and r.ri_base is not None
            and (r.age_min, r.age_max) not in excluded
        ]
        if not values:
            deviations.append(f"{code}: no rows to compare")
            continue

        low, high = min(values), max(values)
        want_low, want_high = float(exp["published_min"]), float(exp["published_max"])
        if abs(low - want_low) > TOLERANCE:
            deviations.append(f"{code}: min {low} != published {want_low}")
        if abs(high - want_high) > TOLERANCE:
            deviations.append(f"{code}: max {high} != published {want_high}")

    return deviations


# ── Task 5: scope filter + pipeline with assertions ─────────────────────

IN_SCOPE_GROUPS = ("vitamin", "mineral")
EXTRA_IN_SCOPE = ("epa_dha",)
ADULT_BANDS = ((19, 29), (30, 49), (50, 64), (65, 74), (75, 99))
EXPECTED_BAND_COUNT = 300


def in_scope_codes(nutrients: dict[str, Nutrient]) -> set[str]:
    codes = {n.code for n in nutrients.values() if n.group in IN_SCOPE_GROUPS}
    return codes | set(EXTRA_IN_SCOPE)


def filter_to_mvp_scope(
    rows: list[KdriRow], nutrients: dict[str, Nutrient]
) -> list[KdriRow]:
    codes = in_scope_codes(nutrients)
    return [
        r
        for r in rows
        if r.nutrient_code in codes
        and (r.age_min, r.age_max) in ADULT_BANDS
        and r.gender in ("M", "F")
        and r.ri_base is not None
    ]


def load_bands(
    vendor_dir: Path = VENDOR_DIR, curated_dir: Path = CURATED_DIR
) -> list[KdriRow]:
    """Full pipeline: load, patch, filter to MVP scope, assert."""
    nutrients = load_nutrients(vendor_dir)
    rows = apply_overrides(load_kdri_rows(vendor_dir), curated_dir)
    bands = filter_to_mvp_scope(rows, nutrients)

    if len(bands) != EXPECTED_BAND_COUNT:
        raise AssertionError(
            f"expected {EXPECTED_BAND_COUNT} adult band rows, got {len(bands)}"
        )
    keys = {(r.nutrient_code, r.gender, r.age_min, r.age_max) for r in bands}
    if len(keys) != EXPECTED_BAND_COUNT:
        raise AssertionError("duplicate (nutrient, sex, band) rows in scope")
    return bands


# ── Task 6: curated limits + profiles ───────────────────────────────────


def load_limits(curated_dir: Path = CURATED_DIR) -> list[Limit]:
    path = curated_dir / "nutrient_limits.csv"
    if not path.exists():
        return []
    out: list[Limit] = []
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if not (row.get("source") or "").strip():
                raise ValueError(f"nutrient_limits.csv row {row} has no source")
            if row["ul_basis"] not in ("total_intake", "supplemental_only"):
                raise ValueError(f"invalid ul_basis in {row}")
            out.append(
                Limit(
                    nutrient_code=row["nutrient_code"],
                    applies_to_form=(row["applies_to_form"] or "").strip() or None,
                    age_min=int(row["age_min"]),
                    age_max=int(row["age_max"]),
                    sex=row["sex"],
                    value=float(row["ul_value"]),
                    unit=row["ul_unit"],
                    basis=row["ul_basis"],
                    source=row["source"],
                )
            )
    return out


def load_profiles(curated_dir: Path = CURATED_DIR) -> dict[str, NutrientProfile]:
    path = curated_dir / "nutrient_profiles.yaml"
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, NutrientProfile] = {}
    for code, body in raw.items():
        forms = tuple(
            Form(
                nutrient_code=code,
                name_ko=f["name_ko"],
                elemental_pct=float(f["elemental_pct"]),
                target_factor=float(f.get("target_factor", 1.0)),
                ul_factor=float(f.get("ul_factor", 1.0)),
                source=f["source"],
            )
            for f in body.get("forms", [])
        )
        guidance = None
        g = body.get("guidance")
        if g is not None:
            if not (g.get("source") or "").strip():
                raise ValueError(f"{code}: guidance block has no source")
            guidance = Guidance(
                recommended_form_ko=(g.get("recommended_form_ko") or "").strip() or None,
                form_reason_ko=(g.get("form_reason_ko") or "").strip() or None,
                timing_ko=(g.get("timing_ko") or "").strip() or None,
                source=g["source"],
            )
        out[code] = NutrientProfile(
            nutrient_code=code,
            target_unit=body["target_unit"],
            ul_unit=body["ul_unit"],
            diet_baseline_pct=body.get("diet_baseline_pct"),
            diet_baseline_source=body.get("diet_baseline_source"),
            forms=forms,
            guidance=guidance,
        )
    return out


# ── Task 14: cited reference CSVs (interactions, energy ratios) ──────────


def _load_cited_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        if not (row.get("source") or "").strip():
            raise ValueError(f"{path.name} row {row} has no source")
    return rows


def load_biomarker_refs(curated_dir: Path = CURATED_DIR) -> list[BiomarkerRef]:
    path = curated_dir / "biomarkers.csv"
    if not path.exists():
        return []
    out: list[BiomarkerRef] = []
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if not (row.get("source") or "").strip():
                raise ValueError(f"biomarkers.csv row {row} has no source")
            if not (row.get("low") or "").strip() and not (row.get("high") or "").strip():
                raise ValueError(f"biomarkers.csv row {row} has neither low nor high bound")
            out.append(
                BiomarkerRef(
                    biomarker_code=row["biomarker_code"],
                    nutrient_code=row["nutrient_code"],
                    sex=row["sex"],
                    low=_opt_float(row["low"]),
                    high=_opt_float(row["high"]),
                    unit=row["unit"],
                    source=row["source"],
                )
            )
    return out


def load_interactions(curated_dir: Path = CURATED_DIR) -> list[dict[str, str]]:
    return _load_cited_csv(curated_dir / "interactions.csv")


def load_energy_ratios(curated_dir: Path = CURATED_DIR) -> list[dict[str, str]]:
    return _load_cited_csv(curated_dir / "energy_ratios.csv")
