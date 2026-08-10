# Supplement Recommendation Engine — Phase 0-1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully tested, deterministic nutrient dose calculator over KDRI 2025 — no UI, no LLM, no database — that computes what an adult should supplement and proves it never recommends past an upper limit.

**Architecture:** Pure functions over frozen dataclasses. Vendor CSVs load, get patched by curated overrides, get validated against the published 2025 ranges, then get filtered to adults 19+ and 30 nutrients. The engine takes loaded tables as arguments and returns a result plus a trace of every rule that fired. Nothing touches I/O below the loader.

**Tech Stack:** Python 3.11+, `pytest`, `PyYAML`. Standard library `csv` for everything else. No database, no web framework, no LLM client in this plan.

**Spec:** [`docs/superpowers/specs/2026-08-10-supplement-recommendation-design.md`](../specs/2026-08-10-supplement-recommendation-design.md)

## Global Constraints

- **The LLM never produces a number.** No LLM client is imported anywhere in this plan. `src/kdri/` must have no import path to any model API.
- **Adults 19+ only.** Age bands `(19,29) (30,49) (50,64) (65,74) (75,99)`. Any profile under 19 raises, never computes.
- **30 nutrients in scope:** `group_name` in (`vitamin`, `mineral`) plus `epa_dha`. That is 14 + 15 + 1.
- **Sex is required and has no default.** No `gender=ALL` row exists for any adult band.
- **Exactly 300 KDRI band rows** survive filtering: 30 nutrients × 5 bands × 2 sexes.
- **Every curated row carries a non-empty `source`.** A value without a citation fails the seed.
- **Pregnancy rows** (`gender=F, age_min=0, age_max=99`) are dropped at load. They are deltas for most nutrients and absolutes for at least one — never usable as-is.
- **`round_down` never rounds toward an upper limit.**
- Money/units: doses are floats in the nutrient's own unit. No unit strings are parsed at runtime; conversion factors come from curated data.

---

## File Structure

```
backend/
  pyproject.toml                     package config, pytest config
  data/
    vendor/                          read-only, never edited by hand
      nutrient_codes.csv             47 rows
      kdri_standards.csv             1052 rows
      2025_KDRI_보도자료.pdf          source document for the range fixture
    curated/                         authored by us, every row cited
      overrides.csv                  vendor value corrections
      nutrient_limits.csv            form-scoped upper limits
      nutrient_profiles.yaml         diet baselines, forms, elemental/conversion factors
      interactions.csv               nutrient × drug class flags
      energy_ratios.csv              AMDR, reference only
  src/kdri/
    __init__.py
    models.py                        all frozen dataclasses + TraceStep
    loader.py                        vendor load, overrides, range check, scope filter, asserts
    lookup.py                        band lookup + 4-step limit resolution
    engine.py                        intake accounting, gap/headroom/recommend, status, priority
  tests/
    conftest.py                      shared fixtures
    fixtures/kdri_2025_ranges.csv    published 2025 ranges, transcribed from the PDF
    test_loader.py
    test_ranges.py
    test_lookup.py
    test_engine.py
    test_golden.py                   the 5 worked examples from spec §6.7
    test_property.py                 exhaustive 300-row UL invariant
    test_curated.py                  citation + completeness coverage (Phase 1)
```

**Why no database.** Spec §5.8 describes seeding to SQLite. The engine takes loaded tables as arguments (spec §6), so Phase 0 needs no persistence to be fully testable. `loader.py` produces in-memory tables and runs the same assertions the spec requires at startup. SQLite lands in Phase 2 with the API and reuses `loader.py` unchanged. This is a deliberate deferral, not a dropped requirement.

---

## Phase 0 — Engine

### Task 1: Project scaffold and vendor data relocation

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/src/kdri/__init__.py`
- Move: `data/*` → `backend/data/vendor/*`
- Test: `backend/tests/test_loader.py`

**Interfaces:**
- Consumes: nothing
- Produces: the `kdri` package importable as `from kdri import ...`; vendor files at `backend/data/vendor/`

- [ ] **Step 1: Move vendor files and rename the PDF**

The current PDF filename contains brackets, plus signs, spaces and a `(1)`, which needs quoting in every shell command forever. Rename it to match the spec.

```bash
mkdir -p backend/data/vendor backend/data/curated backend/src/kdri backend/tests/fixtures
git mv data/kdri_standards.csv backend/data/vendor/kdri_standards.csv
git mv data/nutrient_codes.csv backend/data/vendor/nutrient_codes.csv
git mv "data/[12.31.수+석간]+영양소+적정+섭취기준+개정 (1).pdf" backend/data/vendor/2025_KDRI_보도자료.pdf
```

- [ ] **Step 2: Create `backend/pyproject.toml`**

```toml
[project]
name = "kdri"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["PyYAML>=6.0"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 3: Create the package marker**

`backend/src/kdri/__init__.py`:

```python
"""Deterministic KDRI 2025 nutrient dose engine."""

DATA_DIR = __import__("pathlib").Path(__file__).resolve().parents[2] / "data"
VENDOR_DIR = DATA_DIR / "vendor"
CURATED_DIR = DATA_DIR / "curated"
```

- [ ] **Step 4: Write the failing test**

`backend/tests/test_loader.py`:

```python
import csv

from kdri import VENDOR_DIR


def test_vendor_files_present_with_expected_row_counts():
    codes = list(csv.DictReader((VENDOR_DIR / "nutrient_codes.csv").open(encoding="utf-8")))
    bands = list(csv.DictReader((VENDOR_DIR / "kdri_standards.csv").open(encoding="utf-8")))
    assert len(codes) == 47
    assert len(bands) == 1052
    assert (VENDOR_DIR / "2025_KDRI_보도자료.pdf").exists()
```

- [ ] **Step 5: Run the test**

```bash
cd backend && python -m pytest tests/test_loader.py -v
```

Expected: PASS, 1 test. If it fails with `ModuleNotFoundError: kdri`, install the package in editable mode: `python -m pip install -e ".[dev]"`.

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "chore: scaffold kdri package and relocate vendor data"
```

---

### Task 2: Domain models and vendor loading

**Files:**
- Create: `backend/src/kdri/models.py`
- Create: `backend/src/kdri/loader.py`
- Modify: `backend/tests/test_loader.py`

**Interfaces:**
- Consumes: `VENDOR_DIR` from Task 1
- Produces:
  - `Nutrient(code, name_ko, group, kdri_unit, synonyms, has_rni, has_ai, has_ul)`
  - `KdriRow(nutrient_code, age_min, age_max, gender, ri_base, ul_limit)`
  - `load_nutrients() -> dict[str, Nutrient]`
  - `load_kdri_rows() -> list[KdriRow]`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_loader.py`:

```python
from kdri.loader import load_kdri_rows, load_nutrients


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
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && python -m pytest tests/test_loader.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'kdri.loader'`.

- [ ] **Step 3: Write `models.py`**

`backend/src/kdri/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

Sex = Literal["M", "F"]
Basis = Literal["total_intake", "supplemental_only"]
Status = Literal["DEFICIT", "ADEQUATE", "OVER", "UNKNOWN"]


@dataclass(frozen=True)
class Nutrient:
    code: str
    name_ko: str
    group: str
    kdri_unit: str
    synonyms: tuple[str, ...]
    has_rni: bool
    has_ai: bool
    has_ul: bool


@dataclass(frozen=True)
class KdriRow:
    nutrient_code: str
    age_min: int
    age_max: int
    gender: str
    ri_base: Optional[float]
    ul_limit: Optional[float]


@dataclass(frozen=True)
class Limit:
    nutrient_code: str
    applies_to_form: Optional[str]
    age_min: int
    age_max: int
    sex: str
    value: float
    unit: str
    basis: Basis
    source: str


@dataclass(frozen=True)
class Form:
    nutrient_code: str
    name_ko: str
    elemental_pct: float
    target_factor: float
    ul_factor: float
    source: str


@dataclass(frozen=True)
class NutrientProfile:
    nutrient_code: str
    target_unit: str
    ul_unit: str
    diet_baseline_pct: Optional[float]
    diet_baseline_source: Optional[str]
    forms: tuple[Form, ...] = ()


@dataclass(frozen=True)
class SupplementIntake:
    nutrient_code: str
    dose: float
    doses_per_day: float = 1.0
    form_ko: Optional[str] = None


@dataclass(frozen=True)
class Profile:
    age: int
    sex: Sex
    supplements: tuple[SupplementIntake, ...] = ()
    medications: tuple[str, ...] = ()
    weight_kg: Optional[float] = None


@dataclass(frozen=True)
class TraceStep:
    rule_id: str
    inputs: dict[str, Any]
    output: Any
    citation: Optional[str] = None


@dataclass
class NutrientResult:
    nutrient_code: str
    status: Status
    target: Optional[float]
    from_diet: float
    from_supplements: float
    gap: float
    headroom: Optional[float]
    recommend: float
    priority_score: float = 0.0
    trace: list[TraceStep] = field(default_factory=list)
```

- [ ] **Step 4: Write `loader.py`**

`backend/src/kdri/loader.py`:

```python
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from kdri import VENDOR_DIR
from kdri.models import KdriRow, Nutrient


def _opt_float(raw: str) -> Optional[float]:
    raw = (raw or "").strip()
    return float(raw) if raw else None


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
```

- [ ] **Step 5: Run to verify it passes**

```bash
cd backend && python -m pytest tests/test_loader.py -v
```

Expected: PASS, 3 tests.

- [ ] **Step 6: Commit**

```bash
git add backend/src/kdri/models.py backend/src/kdri/loader.py backend/tests/test_loader.py
git commit -m "feat: load vendor KDRI CSVs into frozen dataclasses"
```

---

### Task 3: Vendor value overrides

**Files:**
- Create: `backend/data/curated/overrides.csv`
- Modify: `backend/src/kdri/loader.py`
- Modify: `backend/tests/test_loader.py`

**Interfaces:**
- Consumes: `load_kdri_rows()` from Task 2
- Produces: `apply_overrides(rows: list[KdriRow], curated_dir: Path = CURATED_DIR) -> list[KdriRow]`

Magnesium `M 15-18 = 410` is a 2020 value surviving in a file labelled 2025; the published 2025 range caps magnesium at 380. Age 15-18 is outside MVP scope, but the correction must land before the range check in Task 4 or that check has to allowlist a real defect.

- [ ] **Step 1: Create `backend/data/curated/overrides.csv`**

```csv
nutrient_code,gender,age_min,age_max,field,value,source,note
magnesium,M,15,18,ri_base,380,"KDRI 2025 보도자료 붙임3 — 마그네슘 70~380","2020 잔존값 410 수정. MVP 범위 밖이나 범위 검증 통과에 필요"
```

- [ ] **Step 2: Write the failing test**

Append to `backend/tests/test_loader.py`:

```python
from kdri.loader import apply_overrides


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
    import pytest

    with pytest.raises(ValueError, match="source"):
        apply_overrides(load_kdri_rows(), curated_dir=tmp_path)
```

- [ ] **Step 3: Run to verify it fails**

```bash
cd backend && python -m pytest tests/test_loader.py -v
```

Expected: FAIL with `ImportError: cannot import name 'apply_overrides'`.

- [ ] **Step 4: Implement `apply_overrides`**

Add to `backend/src/kdri/loader.py` — update the import line at the top to `from kdri import CURATED_DIR, VENDOR_DIR`, then append:

```python
import dataclasses


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
```

- [ ] **Step 5: Run to verify it passes**

```bash
cd backend && python -m pytest tests/test_loader.py -v
```

Expected: PASS, 5 tests.

- [ ] **Step 6: Commit**

```bash
git add backend/data/curated/overrides.csv backend/src/kdri/loader.py backend/tests/test_loader.py
git commit -m "feat: apply cited vendor value overrides, fixing stale magnesium 15-18"
```

---

### Task 4: The 2025 published-range fixture

**Files:**
- Create: `backend/tests/fixtures/kdri_2025_ranges.csv`
- Modify: `backend/src/kdri/loader.py`
- Create: `backend/tests/test_ranges.py`

**Interfaces:**
- Consumes: `load_nutrients()`, `load_kdri_rows()`, `apply_overrides()`
- Produces: `check_published_ranges(rows, nutrients, fixture_path) -> list[str]` returning human-readable deviation strings, empty when clean

Attachment 3 of the press release publishes a min-max for every nutrient. The comparison rule is not "all rows" — the published range covers the nutrient's **own reference type**:

- `has_rni = true` → range spans RNI bands only, so the infant month bands `(0,5)` and `(6,11)` are excluded
- `has_rni = false` → AI nutrient, range spans every band including infants

Pregnancy rows `(0,99)` are excluded either way. Under this rule 28 of 30 nutrients match exactly, which is what makes the remaining two meaningful rather than noise.

- [ ] **Step 1: Create `backend/tests/fixtures/kdri_2025_ranges.csv`**

```csv
nutrient_code,published_min,published_max,allowlisted,reason
vitamin_a,250,850,false,
vitamin_d,5,15,false,
vitamin_e,3,12,false,
vitamin_k,4,80,false,
vitamin_c,40,100,false,
thiamin,0.4,1.3,false,
riboflavin,0.5,1.7,false,
niacin,5,16,false,
vitamin_b6,0.6,1.5,false,
folate,150,400,false,
vitamin_b12,0.9,2.4,false,
pantothenic_acid,1.7,5,false,
biotin,5,30,false,
choline,110,480,false,
calcium,450,950,false,
phosphorus,450,1200,false,
sodium,110,1500,false,
chloride,170,2300,false,
potassium,400,3500,false,
magnesium,70,380,false,
iron,6,13,false,
zinc,3,10,false,
copper,290,900,false,
fluoride,0.01,3.5,false,
manganese,0.01,4.0,false,
iodine,70,150,false,
selenium,23,65,false,
molybdenum,10,40,false,
chromium,0.2,35,false,
epa_dha,100,300,true,"공표 범위 하한 100은 영아 구간, 상한 300은 임신·수유부 구간에서 유래. 벤더 데이터에 영아 행이 없고 임신 행은 seed 단계에서 제외되므로 150~250이 정상"
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_ranges.py`:

```python
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
```

- [ ] **Step 3: Run to verify it fails**

```bash
cd backend && python -m pytest tests/test_ranges.py -v
```

Expected: FAIL with `ImportError: cannot import name 'check_published_ranges'`.

- [ ] **Step 4: Implement `check_published_ranges`**

Append to `backend/src/kdri/loader.py`:

```python
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
```

- [ ] **Step 5: Run to verify it passes**

```bash
cd backend && python -m pytest tests/test_ranges.py -v
```

Expected: PASS, 2 tests.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/fixtures/kdri_2025_ranges.csv backend/tests/test_ranges.py backend/src/kdri/loader.py
git commit -m "test: validate vendor data against published KDRI 2025 ranges"
```

---

### Task 5: Scope filtering and seed assertions

**Files:**
- Modify: `backend/src/kdri/loader.py`
- Modify: `backend/tests/test_loader.py`

**Interfaces:**
- Consumes: everything from Tasks 2-4
- Produces:
  - `IN_SCOPE_GROUPS = ("vitamin", "mineral")`
  - `in_scope_codes(nutrients) -> set[str]`
  - `filter_to_mvp_scope(rows, nutrients) -> list[KdriRow]`
  - `load_bands() -> list[KdriRow]` — the full pipeline, with assertions

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_loader.py`:

```python
from kdri.loader import filter_to_mvp_scope, in_scope_codes, load_bands


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
    # 30 nutrients x 5 bands x 2 sexes, no duplicates
    keys = {(r.nutrient_code, r.gender, r.age_min, r.age_max) for r in rows}
    assert len(keys) == 300


def test_load_bands_runs_the_full_pipeline():
    assert len(load_bands()) == 300
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && python -m pytest tests/test_loader.py -v
```

Expected: FAIL with `ImportError: cannot import name 'filter_to_mvp_scope'`.

- [ ] **Step 3: Implement filtering and the pipeline**

Append to `backend/src/kdri/loader.py`:

```python
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
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: PASS, 10 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/src/kdri/loader.py backend/tests/test_loader.py
git commit -m "feat: filter KDRI data to MVP scope with rectangularity assertions"
```

---

### Task 6: Curated profiles, forms, and limits

**Files:**
- Create: `backend/data/curated/nutrient_limits.csv`
- Create: `backend/data/curated/nutrient_profiles.yaml`
- Modify: `backend/src/kdri/loader.py`
- Create: `backend/tests/test_curated.py`

**Interfaces:**
- Consumes: `CURATED_DIR`
- Produces:
  - `load_limits(curated_dir) -> list[Limit]`
  - `load_profiles(curated_dir) -> dict[str, NutrientProfile]`

Phase 0 authors only the nutrients the golden tests need. Phase 1 (Task 13) completes all 30.

- [ ] **Step 1: Create `backend/data/curated/nutrient_limits.csv`**

```csv
nutrient_code,applies_to_form,age_min,age_max,sex,ul_value,ul_unit,ul_basis,source
magnesium,,19,99,ALL,350,mg,supplemental_only,"KDRI 2025 마그네슘 상한섭취량 — 식품 외 급원에만 적용"
niacin,니코틴산,19,99,ALL,35,mg NE,supplemental_only,"KDRI 2025 보도자료 p.9 — 니코틴산 상한치 2020년 수준 유지"
niacin,니코틴아미드,19,99,ALL,850,mg NE,supplemental_only,"KDRI 2025 보도자료 p.10 — 니코틴아미드 1,000→850 하향"
folate,,19,99,ALL,1000,µg,supplemental_only,"KDRI 2025 보도자료 p.10 — 상한섭취량은 µg/일 유지"
```

- [ ] **Step 2: Create `backend/data/curated/nutrient_profiles.yaml`**

`diet_baseline_pct` values here are provisional and marked as such. Task 13 replaces every one with a KNHANES-sourced figure. Golden tests build their own profiles in-test so they do not depend on these numbers.

```yaml
magnesium:
  target_unit: mg
  ul_unit: mg
  diet_baseline_pct: 0.70
  diet_baseline_source: "PROVISIONAL — KNHANES 출처 확정 필요 (Task 13)"
  forms:
    - name_ko: 산화마그네슘
      elemental_pct: 0.603
      source: "MgO 분자량 40.30/24.31"
    - name_ko: 구연산마그네슘
      elemental_pct: 0.161
      source: "구연산마그네슘 분자량 기준"
    - name_ko: 마그네슘 비스글리시네이트
      elemental_pct: 0.141
      source: "비스글리시네이트 킬레이트 분자량 기준"

niacin:
  target_unit: mg NE
  ul_unit: mg NE
  diet_baseline_pct: 0.90
  diet_baseline_source: "PROVISIONAL — KNHANES 출처 확정 필요 (Task 13)"
  forms:
    - name_ko: 니코틴아미드
      elemental_pct: 1.0
      source: "니아신 등량"
    - name_ko: 니코틴산
      elemental_pct: 1.0
      source: "니아신 등량"

folate:
  target_unit: µg DFE
  ul_unit: µg
  diet_baseline_pct: 0.40
  diet_baseline_source: "PROVISIONAL — KNHANES 출처 확정 필요 (Task 13)"
  forms:
    - name_ko: 엽산
      elemental_pct: 1.0
      target_factor: 1.7
      ul_factor: 1.0
      source: "KDRI 2025 보도자료 p.10 — 합성 엽산 1µg = 1.7µg DFE (식사와 함께)"
    - name_ko: 메틸엽산
      elemental_pct: 1.0
      target_factor: 1.7
      ul_factor: 1.0
      source: "KDRI 2025 보도자료 p.10"

iron:
  target_unit: mg
  ul_unit: mg
  diet_baseline_pct: 0.60
  diet_baseline_source: "PROVISIONAL — KNHANES 출처 확정 필요 (Task 13)"
  forms:
    - name_ko: 푸마르산철
      elemental_pct: 0.329
      source: "푸마르산제일철 분자량 기준"
```

- [ ] **Step 3: Write the failing test**

`backend/tests/test_curated.py`:

```python
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
```

- [ ] **Step 4: Run to verify it fails**

```bash
cd backend && python -m pytest tests/test_curated.py -v
```

Expected: FAIL with `ImportError: cannot import name 'load_limits'`.

- [ ] **Step 5: Implement the curated loaders**

Append to `backend/src/kdri/loader.py` — add `import yaml` at the top and `from kdri.models import Form, KdriRow, Limit, Nutrient, NutrientProfile` to the models import:

```python
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
        out[code] = NutrientProfile(
            nutrient_code=code,
            target_unit=body["target_unit"],
            ul_unit=body["ul_unit"],
            diet_baseline_pct=body.get("diet_baseline_pct"),
            diet_baseline_source=body.get("diet_baseline_source"),
            forms=forms,
        )
    return out
```

- [ ] **Step 6: Run to verify it passes**

```bash
cd backend && python -m pytest tests/test_curated.py -v
```

Expected: PASS, 5 tests.

- [ ] **Step 7: Commit**

```bash
git add backend/data/curated backend/src/kdri/loader.py backend/tests/test_curated.py
git commit -m "feat: load form-scoped limits and nutrient profiles from curated files"
```

---

### Task 7: Band lookup and limit resolution

**Files:**
- Create: `backend/src/kdri/lookup.py`
- Create: `backend/tests/test_lookup.py`

**Interfaces:**
- Consumes: `KdriRow`, `Limit`, `NutrientProfile` from Task 2 and Task 6
- Produces:
  - `find_band(bands, nutrient_code, sex, age) -> KdriRow`
  - `resolve_limit(limits, band, nutrient_code, declared_forms, age, sex, ul_unit) -> Limit | None`
  - `find_form(profile, form_ko) -> Form | None`
  - `BandNotFound(LookupError)`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_lookup.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && python -m pytest tests/test_lookup.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'kdri.lookup'`.

- [ ] **Step 3: Implement `lookup.py`**

`backend/src/kdri/lookup.py`:

```python
from __future__ import annotations

from typing import Iterable, Optional

from kdri.models import Form, KdriRow, Limit, NutrientProfile


class BandNotFound(LookupError):
    """No KDRI band matches the requested nutrient, sex, and age."""


def find_band(
    bands: list[KdriRow], nutrient_code: str, sex: str, age: int
) -> KdriRow:
    for band in bands:
        if (
            band.nutrient_code == nutrient_code
            and band.gender == sex
            and band.age_min <= age <= band.age_max
        ):
            return band
    raise BandNotFound(f"no band for {nutrient_code} sex={sex} age={age}")


def _applies(limit: Limit, age: int, sex: str) -> bool:
    if not (limit.age_min <= age <= limit.age_max):
        return False
    return limit.sex in ("ALL", sex)


def resolve_limit(
    limits: list[Limit],
    band: KdriRow,
    nutrient_code: str,
    declared_forms: Iterable[Optional[str]],
    age: int,
    sex: str,
    ul_unit: str,
) -> Optional[Limit]:
    """Four-step resolution, most specific first (spec section 5.3)."""
    forms = [f for f in declared_forms if f]

    # 1. a limit written for one of the forms the user actually declared
    for form in forms:
        for limit in limits:
            if (
                limit.nutrient_code == nutrient_code
                and limit.applies_to_form == form
                and _applies(limit, age, sex)
            ):
                return limit

    # 2. a nutrient-wide limit covering all supplemental forms
    for limit in limits:
        if (
            limit.nutrient_code == nutrient_code
            and limit.applies_to_form is None
            and _applies(limit, age, sex)
        ):
            return limit

    # 3. the vendor band's own upper limit, which is always total-intake based
    if band.ul_limit is not None:
        return Limit(
            nutrient_code=nutrient_code,
            applies_to_form=None,
            age_min=band.age_min,
            age_max=band.age_max,
            sex=sex,
            value=band.ul_limit,
            unit=ul_unit,
            basis="total_intake",
            source="KDRI 2025 vendor table",
        )

    # 4. no established upper limit
    return None


def find_form(
    profile: Optional[NutrientProfile], form_ko: Optional[str]
) -> Optional[Form]:
    if profile is None or not form_ko:
        return None
    for form in profile.forms:
        if form.name_ko == form_ko:
            return form
    return None
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd backend && python -m pytest tests/test_lookup.py -v
```

Expected: PASS, 8 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/src/kdri/lookup.py backend/tests/test_lookup.py
git commit -m "feat: band lookup and four-step form-scoped limit resolution"
```

---

### Task 8: Intake accounting and core computation

**Files:**
- Create: `backend/src/kdri/engine.py`
- Create: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: everything from Tasks 6-7
- Produces:
  - `round_down(value: float, sig: int = 2) -> float`
  - `accumulate(profile, intakes) -> tuple[float, float]` returning `(toward_target, toward_limit)`
  - `compute_nutrient(nutrient_code, profile, bands, limits, profiles) -> NutrientResult`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_engine.py`:

```python
import pytest

from kdri.engine import accumulate, compute_nutrient, round_down
from kdri.loader import load_bands, load_limits, load_profiles
from kdri.models import Profile, SupplementIntake


@pytest.fixture(scope="module")
def tables():
    return load_bands(), load_limits(), load_profiles()


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
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && python -m pytest tests/test_engine.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'kdri.engine'`.

- [ ] **Step 3: Implement `engine.py`**

`backend/src/kdri/engine.py`:

```python
from __future__ import annotations

import math
from typing import Iterable, Optional

from kdri.lookup import BandNotFound, find_band, find_form, resolve_limit
from kdri.models import (
    KdriRow,
    Limit,
    NutrientProfile,
    NutrientResult,
    Profile,
    SupplementIntake,
    TraceStep,
)

MIN_ADULT_AGE = 19


def round_down(value: float, sig: int = 2) -> float:
    """Round toward zero to `sig` significant figures. Never rounds up."""
    if value <= 0:
        return 0.0
    magnitude = math.floor(math.log10(value)) - (sig - 1)
    step = 10.0**magnitude
    return math.floor(value / step) * step


def accumulate(
    profile: Optional[NutrientProfile], intakes: Iterable[SupplementIntake]
) -> tuple[float, float]:
    """Return (toward_target, toward_limit) — one pill can produce two numbers."""
    toward_target = 0.0
    toward_limit = 0.0
    for intake in intakes:
        form = find_form(profile, intake.form_ko)
        elemental = form.elemental_pct if form else 1.0
        target_factor = form.target_factor if form else 1.0
        ul_factor = form.ul_factor if form else 1.0
        base = intake.dose * elemental * intake.doses_per_day
        toward_target += base * target_factor
        toward_limit += base * ul_factor
    return toward_target, toward_limit


def compute_nutrient(
    nutrient_code: str,
    user: Profile,
    bands: list[KdriRow],
    limits: list[Limit],
    profiles: dict[str, NutrientProfile],
) -> NutrientResult:
    if user.age < MIN_ADULT_AGE:
        raise ValueError(f"age {user.age} is outside MVP scope (adults {MIN_ADULT_AGE}+)")

    trace: list[TraceStep] = []
    nutrient_profile = profiles.get(nutrient_code)
    intakes = [s for s in user.supplements if s.nutrient_code == nutrient_code]

    try:
        band = find_band(bands, nutrient_code, user.sex, user.age)
    except BandNotFound:
        return NutrientResult(
            nutrient_code=nutrient_code,
            status="UNKNOWN",
            target=None,
            from_diet=0.0,
            from_supplements=0.0,
            gap=0.0,
            headroom=None,
            recommend=0.0,
            trace=[TraceStep("band.missing", {"sex": user.sex, "age": user.age}, None)],
        )

    target = band.ri_base
    trace.append(
        TraceStep(
            "target.from_band",
            {"sex": user.sex, "age": user.age, "band": (band.age_min, band.age_max)},
            target,
            "KDRI 2025",
        )
    )

    toward_target, toward_limit = accumulate(nutrient_profile, intakes)
    trace.append(
        TraceStep(
            "intake.accumulated",
            {"items": len(intakes)},
            {"toward_target": toward_target, "toward_limit": toward_limit},
        )
    )

    ul_unit = nutrient_profile.ul_unit if nutrient_profile else band_unit_unknown()
    limit = resolve_limit(
        limits,
        band,
        nutrient_code,
        [s.form_ko for s in intakes],
        user.age,
        user.sex,
        ul_unit,
    )

    if limit is None:
        headroom = None
    elif limit.basis == "supplemental_only":
        headroom = limit.value - toward_limit
    else:
        headroom = None  # filled in below once diet is known

    baseline = nutrient_profile.diet_baseline_pct if nutrient_profile else None
    if baseline is None:
        trace.append(TraceStep("baseline.unknown", {"nutrient": nutrient_code}, None))
        return NutrientResult(
            nutrient_code=nutrient_code,
            status="UNKNOWN",
            target=target,
            from_diet=0.0,
            from_supplements=toward_target,
            gap=0.0,
            headroom=headroom,
            recommend=0.0,
            trace=trace,
        )

    from_diet = target * baseline
    trace.append(
        TraceStep(
            "diet.baseline",
            {"target": target, "pct": baseline},
            from_diet,
            nutrient_profile.diet_baseline_source,
        )
    )

    if limit is not None and limit.basis == "total_intake":
        headroom = limit.value - from_diet - toward_limit

    gap = max(0.0, target - from_diet - toward_target)
    recommend = gap if headroom is None else min(gap, headroom)
    recommend = round_down(max(0.0, recommend))

    if headroom is not None and headroom < 0:
        status = "OVER"
    elif gap > 0:
        status = "DEFICIT"
    else:
        status = "ADEQUATE"

    trace.append(
        TraceStep(
            "recommend.computed",
            {"gap": gap, "headroom": headroom, "basis": limit.basis if limit else None},
            recommend,
            limit.source if limit else None,
        )
    )

    return NutrientResult(
        nutrient_code=nutrient_code,
        status=status,
        target=target,
        from_diet=from_diet,
        from_supplements=toward_target,
        gap=gap,
        headroom=headroom,
        recommend=recommend,
        trace=trace,
    )


def band_unit_unknown() -> str:
    return "unknown"
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd backend && python -m pytest tests/test_engine.py -v
```

Expected: PASS, 7 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/src/kdri/engine.py backend/tests/test_engine.py
git commit -m "feat: dual-accounting intake and core dose computation with trace"
```

---

### Task 9: The five golden cases

**Files:**
- Create: `backend/tests/test_golden.py`

**Interfaces:**
- Consumes: `compute_nutrient`, `load_bands`, `load_limits`, `load_profiles`
- Produces: nothing consumed downstream

Each case is a number that a plausible wrong implementation gets wrong **silently** — no crash, no exception, just a confident bad recommendation. Golden tests build their own `NutrientProfile` objects so they stay stable when Task 13 replaces the provisional diet baselines.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_golden.py`:

```python
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
    """400 mg of bisglycinate is 56.4 mg elemental, not 400.

    Reading the label as elemental gives gap 0 and tells the user they are fine.
    They are 58 mg short.
    """
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
    """The supplemental-only basis must exclude diet, or RI 380 > UL 350 breaks.

    Computing headroom as 350 - diet - current reports a healthy adult as
    dangerously over-supplemented before they take anything.
    """
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
    """500 mg nicotinamide is inside its 850 limit.

    Reading the band's 35 (the nicotinic acid figure) gives headroom -465 and
    tells the user to stop a supplement that is within its actual limit.
    """
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
    """200 ug folic acid is 340 ug DFE toward target but 200 ug toward the limit.

    Treating the label as DFE gives gap 40 and recommends more folate to
    someone already at target.
    """
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
```

- [ ] **Step 2: Run to verify it fails, then passes**

```bash
cd backend && python -m pytest tests/test_golden.py -v
```

Expected: PASS, 7 tests. If any fail, the engine is wrong — these numbers are hand-computed in the spec, not derived from the implementation.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_golden.py
git commit -m "test: five golden cases covering elemental, basis, form, and unit traps"
```

---

### Task 10: Exhaustive upper-limit property test

**Files:**
- Create: `backend/tests/test_property.py`

**Interfaces:**
- Consumes: `compute_nutrient`, `load_bands`, `load_limits`
- Produces: nothing consumed downstream

Adult scope is rectangular — 30 nutrients × 5 bands × 2 sexes with no gaps — so enumerating every combination is genuinely exhaustive, not sampled. The test supplies its own diet baseline so it does not depend on curated content that Phase 1 will change.

- [ ] **Step 1: Write the test**

`backend/tests/test_property.py`:

```python
"""Exhaustive invariant check across all 300 adult band rows.

The engine must never recommend a dose that pushes intake past an upper limit,
for any nutrient, band, sex, or starting intake level.
"""

import dataclasses

import pytest

from kdri.engine import compute_nutrient, round_down
from kdri.loader import load_bands, load_limits, load_profiles
from kdri.models import NutrientProfile, Profile, SupplementIntake

BAND_MIDPOINTS = {(19, 29): 25, (30, 49): 40, (50, 64): 57, (65, 74): 70, (75, 99): 80}
INTAKE_FRACTIONS = (0.0, 0.5, 1.0, 5.0)
TOLERANCE = 1e-9


@pytest.fixture(scope="module")
def tables():
    return load_bands(), load_limits()


def baseline_profiles(bands) -> dict[str, NutrientProfile]:
    """A 0.5 diet baseline for every in-scope nutrient, forms preserved."""
    curated = load_profiles()
    out: dict[str, NutrientProfile] = {}
    for code in {b.nutrient_code for b in bands}:
        existing = curated.get(code)
        if existing is not None:
            out[code] = dataclasses.replace(existing, diet_baseline_pct=0.5)
        else:
            out[code] = NutrientProfile(
                nutrient_code=code,
                target_unit="unit",
                ul_unit="unit",
                diet_baseline_pct=0.5,
                diet_baseline_source="TEST",
            )
    return out


def test_every_adult_band_respects_its_upper_limit(tables):
    bands, limits = tables
    profiles = baseline_profiles(bands)
    assert len(bands) == 300

    checked = 0
    for band in bands:
        age = BAND_MIDPOINTS[(band.age_min, band.age_max)]
        for fraction in INTAKE_FRACTIONS:
            dose = (band.ri_base or 0.0) * fraction
            user = Profile(
                age=age,
                sex=band.gender,
                supplements=(
                    (SupplementIntake(band.nutrient_code, dose=dose),) if dose else ()
                ),
            )
            result = compute_nutrient(
                band.nutrient_code, user, bands, limits, profiles
            )
            checked += 1

            assert result.recommend >= 0.0, result
            assert result.recommend <= result.gap + TOLERANCE, result
            if result.headroom is not None:
                assert result.recommend <= max(0.0, result.headroom) + TOLERANCE, result
            else:
                # 12 of 30 nutrients have no established UL. Absence of a
                # ceiling must never mean an unbounded dose: the target caps it.
                assert result.recommend == round_down(result.gap), result

    assert checked == 300 * len(INTAKE_FRACTIONS)


def test_recommendation_never_pushes_total_past_the_limit(tables):
    bands, limits = tables
    profiles = baseline_profiles(bands)

    for band in bands:
        age = BAND_MIDPOINTS[(band.age_min, band.age_max)]
        user = Profile(age=age, sex=band.gender)
        result = compute_nutrient(band.nutrient_code, user, bands, limits, profiles)
        if result.headroom is None or result.status == "OVER":
            continue
        consumed = result.from_supplements
        if result.headroom is not None:
            assert consumed + result.recommend <= (
                result.from_supplements + result.headroom + TOLERANCE
            ), result
```

- [ ] **Step 2: Run the test**

```bash
cd backend && python -m pytest tests/test_property.py -v
```

Expected: PASS, 2 tests, 1200 combinations checked.

- [ ] **Step 3: Run the whole suite**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: PASS, roughly 31 tests.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_property.py
git commit -m "test: exhaustive UL invariant across all 300 adult band rows"
```

---

### Task 11: Priority ordering and the full report

**Files:**
- Modify: `backend/src/kdri/engine.py`
- Modify: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `compute_nutrient`
- Produces: `compute_report(user, bands, limits, profiles) -> list[NutrientResult]` sorted by priority

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_engine.py`:

```python
from kdri.engine import compute_report


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
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && python -m pytest tests/test_engine.py -v
```

Expected: FAIL with `ImportError: cannot import name 'compute_report'`.

- [ ] **Step 3: Implement `compute_report`**

Append to `backend/src/kdri/engine.py`:

```python
STATUS_RANK = {"OVER": 0, "DEFICIT": 1, "ADEQUATE": 2, "UNKNOWN": 3}


def _priority(result: NutrientResult) -> tuple[int, float]:
    rank = STATUS_RANK[result.status]
    if result.status == "DEFICIT" and result.target:
        # larger shortfall relative to target sorts earlier
        return (rank, -(result.gap / result.target))
    return (rank, 0.0)


def compute_report(
    user: Profile,
    bands: list[KdriRow],
    limits: list[Limit],
    profiles: dict[str, NutrientProfile],
) -> list[NutrientResult]:
    if user.age < MIN_ADULT_AGE:
        raise ValueError(f"age {user.age} is outside MVP scope (adults {MIN_ADULT_AGE}+)")

    codes = sorted({b.nutrient_code for b in bands})
    results = [
        compute_nutrient(code, user, bands, limits, profiles) for code in codes
    ]
    results.sort(key=_priority)
    for result in results:
        result.priority_score = float(STATUS_RANK[result.status])
    return results
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: PASS, roughly 35 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/src/kdri/engine.py backend/tests/test_engine.py
git commit -m "feat: full-report computation with safety-first priority ordering"
```

---

### Task 12: Trace completeness

**Files:**
- Modify: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `compute_report`
- Produces: nothing consumed downstream

The why-chat (Phase 6) is read-only and answers strictly from the trace. If a number reaches the report without a trace step, that chat cannot explain it and will either refuse or improvise. This test is what keeps that honest as the engine grows.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_engine.py`:

```python
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
```

- [ ] **Step 2: Run the tests**

```bash
cd backend && python -m pytest tests/test_engine.py -v
```

Expected: PASS. If `test_trace_records_the_limit_source_when_one_applies` fails, `compute_nutrient` is dropping `limit.source` — fix the `recommend.computed` TraceStep rather than the test.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_engine.py
git commit -m "test: assert every reported number is reachable from a trace step"
```

---

## Phase 1 — Curated content

### Task 13: Complete nutrient profiles for all 30

**Files:**
- Modify: `backend/data/curated/nutrient_profiles.yaml`
- Modify: `backend/tests/test_curated.py`

**Interfaces:**
- Consumes: `load_profiles`, `in_scope_codes`
- Produces: a complete, cited profile for every in-scope nutrient

Every `diet_baseline_pct` must trace to a named KNHANES table and year. Where KNHANES has no figure, set `diet_baseline_pct: null` and `diet_baseline_source: none` — the engine already returns `UNKNOWN` for those and declines to produce a number, which is the correct outcome. Guessing a baseline systematically over-recommends.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_curated.py`:

```python
from kdri.loader import in_scope_codes, load_nutrients


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
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && python -m pytest tests/test_curated.py -v
```

Expected: FAIL — 26 nutrients missing, and the four Phase 0 baselines still say `PROVISIONAL`.

- [ ] **Step 3: Author the remaining 26 profiles**

Extend `nutrient_profiles.yaml` with one block per remaining in-scope nutrient. Required keys per nutrient: `target_unit`, `ul_unit`, `diet_baseline_pct`, `diet_baseline_source`. `forms` is required only where a supplement form changes the elemental content or the unit — for nutrients sold as the nutrient itself, omit `forms` and the engine treats the label value as elemental.

Replace the four `PROVISIONAL` sources with real KNHANES citations in the same pass.

To list what still needs writing:

```bash
cd backend && python -c "from kdri.loader import in_scope_codes, load_nutrients, load_profiles; print(sorted(in_scope_codes(load_nutrients()) - set(load_profiles())))"
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: PASS, all tests.

- [ ] **Step 5: Commit**

```bash
git add backend/data/curated/nutrient_profiles.yaml backend/tests/test_curated.py
git commit -m "feat: cited diet baselines and supplement forms for all 30 nutrients"
```

---

### Task 14: Interactions and AMDR reference data

**Files:**
- Create: `backend/data/curated/interactions.csv`
- Create: `backend/data/curated/energy_ratios.csv`
- Modify: `backend/src/kdri/loader.py`
- Modify: `backend/tests/test_curated.py`

**Interfaces:**
- Produces:
  - `load_interactions(curated_dir) -> list[dict]`
  - `load_energy_ratios(curated_dir) -> list[dict]`

`energy_ratios` is reference data. The engine must never read it — an AMDR is a percentage of actual energy intake, and diet logging is out of scope, so there is no denominator.

- [ ] **Step 1: Create `backend/data/curated/interactions.csv`**

```csv
nutrient_code,drug_class,drug_examples_ko,effect,action,severity,source
calcium,levothyroxine,"레보티록신(씬지로이드)",흡수저해,4시간 이상 간격 두기,high,"약물-영양소 상호작용 가이드"
magnesium,quinolone,"시프로플록사신, 레보플록사신",킬레이트 형성으로 흡수저해,2시간 이상 간격 두기,high,"약물-영양소 상호작용 가이드"
calcium,quinolone,"시프로플록사신, 레보플록사신",킬레이트 형성으로 흡수저해,2시간 이상 간격 두기,high,"약물-영양소 상호작용 가이드"
iron,proton_pump_inhibitor,"오메프라졸, 판토프라졸",위산 감소로 흡수저해,담당의와 상담,medium,"약물-영양소 상호작용 가이드"
vitamin_k,warfarin,"와파린",항응고 효과 길항,담당의 상담 필수,critical,"약물-영양소 상호작용 가이드"
vitamin_b12,metformin,"메트포르민",장기 복용 시 흡수저해,정기적 수치 확인,medium,"약물-영양소 상호작용 가이드"
```

Sources above are placeholders for the review pass — Step 3 requires each to name a specific reference before the test passes.

- [ ] **Step 2: Create `backend/data/curated/energy_ratios.csv`**

```csv
macronutrient,age_min,age_max,pct_min,pct_max,kdri_version,source,changed_2025
carbohydrate,1,99,50,65,2025,"KDRI 2025 보도자료 p.7","하한선 하향 (55→50)"
protein,1,99,10,20,2025,"KDRI 2025 보도자료 p.7","하한선 상향 (7→10)"
fat,1,99,15,30,2025,"KDRI 2025 보도자료 p.7","유지"
```

- [ ] **Step 3: Write the failing test**

Append to `backend/tests/test_curated.py`:

```python
from kdri.loader import load_energy_ratios, load_interactions


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
```

- [ ] **Step 4: Implement the two loaders**

Append to `backend/src/kdri/loader.py`:

```python
def _load_cited_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        if not (row.get("source") or "").strip():
            raise ValueError(f"{path.name} row {row} has no source")
    return rows


def load_interactions(curated_dir: Path = CURATED_DIR) -> list[dict[str, str]]:
    return _load_cited_csv(curated_dir / "interactions.csv")


def load_energy_ratios(curated_dir: Path = CURATED_DIR) -> list[dict[str, str]]:
    return _load_cited_csv(curated_dir / "energy_ratios.csv")
```

- [ ] **Step 5: Replace the placeholder interaction sources**

Each `source` must name a specific reference (a monograph, a labelled drug insert, or a published interaction table). The test rejects the generic placeholder.

- [ ] **Step 6: Run the full suite**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: PASS, all tests.

- [ ] **Step 7: Commit**

```bash
git add backend/data/curated backend/src/kdri/loader.py backend/tests/test_curated.py
git commit -m "feat: cited drug interaction table and AMDR reference data"
```

---

## Phases 2-7 — Roadmap

These are deliberately not expanded into TDD steps yet. Each depends on signatures that only firm up once the engine exists, and writing them now would produce the placeholder steps this plan format forbids. Each gets its own full plan as its predecessor lands.

### Phase 2 — API and report page

| Task | Files | Produces |
|---|---|---|
| SQLite persistence | `src/kdri/db.py`, `alembic/` | Seeds `loader.py` output into SQLite; same assertions run at startup |
| Report endpoints | `src/kdri/api/reports.py` | `POST /reports` → `Report`, `GET /reports/{id}` |
| Intake wizard | `frontend/app/intake/` | Age, sex, supplements, medications; sex required with an explanation |
| Report page | `frontend/app/reports/[id]/` | The four blocks from spec §9, each number expandable to its trace |

### Phase 3 — Manual entry and the confirm screen

| Task | Files | Produces |
|---|---|---|
| Text parser | `src/kdri/llm/parse.py` | Free text → `list[SupplementIntake]`, validated against `Nutrient.synonyms` |
| Confirm screen | `frontend/app/intake/confirm/` | The trust boundary — nothing reaches the engine unapproved |

### Phase 4 — OCR

| Task | Files | Produces |
|---|---|---|
| Vision extraction | `src/kdri/llm/ocr.py` | Bottle photo → raw text, then Phase 3's parser unchanged |
| Photo upload | `frontend/app/intake/photo/` | Converges on the same confirm screen |

### Phase 5 — Sensitivity-driven follow-ups

| Task | Files | Produces |
|---|---|---|
| Gap detector | `src/kdri/sensitivity.py` | Re-runs the engine with each missing field pinned to min and max; ranks by swing |
| Question phrasing | `src/kdri/llm/questions.py` | Korean phrasing of the engine's ranked list, cannot invent off-list questions |

### Phase 6 — Why-chat

| Task | Files | Produces |
|---|---|---|
| Trace serialization | `src/kdri/trace.py` | `TraceStep` list → chat context JSON |
| Chat endpoint | `src/kdri/api/chat.py` | Read-only, refuses new dosing, bound to one report version |

### Phase 7 — Auth, history, versioning

| Task | Files | Produces |
|---|---|---|
| Magic link auth | `src/kdri/api/auth.py` | Email token issue and verify, no passwords |
| Report versioning | `src/kdri/api/reports.py` | `parent_id` chains; edit inputs re-runs the engine into a new version |
| History | `frontend/app/history/` | Revision chains per user |

---

## Self-Review

**Spec coverage.** Every §5 data file has a task: overrides (3), limits and profiles (6), interactions and energy ratios (14). §5.8 seed assertions land in Tasks 3, 5, 6, 13, 14. §6.2 computation is Task 8; §6.3's three traps are Tasks 7 and 9. §6.4 status is Task 8, §6.5 priority is Task 11, §6.6 trace is Tasks 8 and 12. §13's three test families are Tasks 4, 9, 10, 12. §5.7 weight is carried on `Profile` and read by nothing, as specified. §§7-12 are Phases 2-7.

**Deliberate deferrals, both stated where they occur:** SQLite moves to Phase 2 because the engine takes tables as arguments; `interactions.csv` loads in Phase 1 but is not consumed until the report renders in Phase 2.

**Type consistency.** `NutrientProfile.diet_baseline_pct` is `Optional[float]` and every reader handles `None`. `Limit.value`/`Limit.basis` are used identically in `lookup.resolve_limit` and `engine.compute_nutrient`. `accumulate` returns `(toward_target, toward_limit)` in that order at all three call sites. `find_form` takes `Optional[NutrientProfile]` because `profiles.get()` can miss.

**Known rough edge.** `band_unit_unknown()` in Task 8 is a stub returning `"unknown"` for nutrients without a curated profile. It only feeds `Limit.unit` on the vendor-band fallback, which nothing compares against in Phase 0. Task 13 gives every in-scope nutrient a profile, after which the stub is unreachable and should be deleted in Phase 2.
