"""Seed the SQLite database from the curated/vendor files via loader.*.

`seed_all` writes every seeded table, runs the erd.md §6 / spec §5.8 assertions,
and aborts (raises) on any failure so bad data never reaches the engine (PF-04).
Idempotent: reseeding wipes and rewrites seeded tables to an identical state
(PF-05). Runtime tables (users/reports/...) are never touched here.
"""

from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from sqlalchemy import delete
from sqlalchemy.orm import Session

from kdri import DATA_DIR
from kdri import loader
from kdri.db import (
    EnergyRatio,
    Interaction,
    KdriBand,
    Nutrient,
    NutrientForm,
    NutrientLimit,
)
from kdri.models import KdriRow, Limit, NutrientProfile

DEMO_BASELINES = DATA_DIR / "demo" / "baselines.yaml"
DEMO_SOURCE = "예시 데이터 — KDRI/KNHANES 미출처, 화면 시연용"


@dataclass
class EngineInputs:
    """Everything the api layer feeds the pure engine + renders around it."""

    nutrients: dict
    bands: list[KdriRow]
    limits: list[Limit]
    profiles: dict[str, NutrientProfile]
    interactions: list[dict]
    energy_ratios: list[dict]
    biomarker_refs: list = field(default_factory=list)
    demo: bool = False
    in_scope: set[str] = field(default_factory=set)


def _apply_demo_overlay(profiles: dict[str, NutrientProfile]) -> dict[str, NutrientProfile]:
    """Overlay illustrative diet_baseline_pct onto profiles (KDRI_DEMO=1).

    Production path stays honest: absent baselines remain null -> UNKNOWN.
    """
    if not DEMO_BASELINES.exists():
        return profiles
    overlay = yaml.safe_load(DEMO_BASELINES.read_text(encoding="utf-8")) or {}
    out = dict(profiles)
    for code, pct in overlay.items():
        if code in out:
            out[code] = dataclasses.replace(
                out[code],
                diet_baseline_pct=float(pct),
                diet_baseline_source=DEMO_SOURCE,
            )
    return out


def load_engine_inputs(demo: bool | None = None) -> EngineInputs:
    """Load all engine inputs from files. `demo` defaults to env KDRI_DEMO=1."""
    if demo is None:
        demo = os.environ.get("KDRI_DEMO") == "1"
    nutrients = loader.load_nutrients()
    profiles = loader.load_profiles()
    if demo:
        profiles = _apply_demo_overlay(profiles)
    return EngineInputs(
        nutrients=nutrients,
        bands=loader.load_bands(),
        limits=loader.load_limits(),
        profiles=profiles,
        interactions=loader.load_interactions(),
        energy_ratios=loader.load_energy_ratios(),
        biomarker_refs=loader.load_biomarker_refs(),
        demo=bool(demo),
        in_scope=loader.in_scope_codes(nutrients),
    )


def run_seed_assertions(inp: EngineInputs) -> None:
    """erd.md §6 / spec §5.8. Raises AssertionError on any violation."""
    bands = inp.bands
    assert len(bands) == 300, f"expected 300 band rows, got {len(bands)}"
    for b in bands:
        assert b.ri_base is not None, f"null ri_base: {b.nutrient_code}"
        assert b.gender in ("M", "F"), f"bad sex {b.gender}: {b.nutrient_code}"
        assert b.age_min >= 19, f"pediatric band survived: {b.nutrient_code}"
        assert (b.age_min, b.age_max) != (0, 99), f"pregnancy band survived: {b.nutrient_code}"

    for code in inp.in_scope:
        prof = inp.profiles.get(code)
        assert prof is not None, f"no profile for in-scope nutrient {code}"
        has_baseline = prof.diet_baseline_pct is not None
        explicit_none = (prof.diet_baseline_source or "").strip().lower() in ("none", "")
        assert has_baseline or explicit_none, (
            f"{code}: baseline neither set nor explicitly 'none'"
        )
        # folate trap: split-unit nutrients must carry forms with factors.
        if prof.target_unit != prof.ul_unit:
            assert prof.forms, f"{code}: split unit but no forms with factors"

    for lim in inp.limits:
        assert lim.basis in ("total_intake", "supplemental_only"), lim
        assert lim.unit and lim.unit.strip(), f"limit missing unit: {lim.nutrient_code}"
        assert lim.source and lim.source.strip(), f"limit missing source: {lim.nutrient_code}"


def _wipe_seeded(session: Session) -> None:
    for model in (KdriBand, NutrientLimit, NutrientForm, Interaction, EnergyRatio):
        session.execute(delete(model))
    session.execute(delete(Nutrient))


def seed_all(session: Session, inputs: EngineInputs | None = None) -> EngineInputs:
    """Load, assert, and write the seeded tables. Idempotent."""
    inp = inputs if inputs is not None else load_engine_inputs()
    run_seed_assertions(inp)

    _wipe_seeded(session)

    for code, prof in inp.profiles.items():
        n = inp.nutrients.get(code)
        if n is None:
            continue
        session.add(
            Nutrient(
                nutrient_code=code,
                nutrient_ko=n.name_ko,
                group_name=n.group,
                target_unit=prof.target_unit,
                ul_unit=prof.ul_unit,
                synonyms_ko_label="|".join(n.synonyms),
                has_rni=n.has_rni,
                has_ai=n.has_ai,
                has_ul=n.has_ul,
            )
        )
        for form in prof.forms:
            session.add(
                NutrientForm(
                    nutrient_code=code,
                    name_ko=form.name_ko,
                    elemental_pct=form.elemental_pct,
                    target_factor=form.target_factor,
                    ul_factor=form.ul_factor,
                    source=form.source,
                )
            )

    session.flush()  # nutrients must exist before their FK children insert

    for b in inp.bands:
        session.add(
            KdriBand(
                nutrient_code=b.nutrient_code,
                sex=b.gender,
                age_min=b.age_min,
                age_max=b.age_max,
                ri_base=b.ri_base,
                ul_limit=b.ul_limit,
            )
        )

    for lim in inp.limits:
        session.add(
            NutrientLimit(
                nutrient_code=lim.nutrient_code,
                applies_to_form=lim.applies_to_form,
                age_min=lim.age_min,
                age_max=lim.age_max,
                sex=lim.sex,
                ul_value=lim.value,
                ul_unit=lim.unit,
                ul_basis=lim.basis,
                source=lim.source,
            )
        )

    for row in inp.interactions:
        session.add(
            Interaction(
                nutrient_code=row["nutrient_code"],
                drug_class=row["drug_class"],
                drug_examples_ko=row.get("drug_examples_ko"),
                effect=row.get("effect"),
                action=row["action"],
                severity=row["severity"],
                source=row["source"],
            )
        )

    for row in inp.energy_ratios:
        session.add(
            EnergyRatio(
                macronutrient=row["macronutrient"],
                age_min=int(row["age_min"]),
                age_max=int(row["age_max"]),
                pct_min=float(row["pct_min"]),
                pct_max=float(row["pct_max"]),
                source=row["source"],
                changed_2025=row.get("changed_2025"),
            )
        )

    session.commit()
    return inp
