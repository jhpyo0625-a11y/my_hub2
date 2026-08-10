# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An AI supplement-recommendation service for Korean adults (19+). A user gives basic facts (age, sex, current supplements, medications, optional biomarkers); the system computes *what to take, how much, and when* against the **2025 한국인 영양소 섭취기준 (KDRI)**. All user-facing output is Korean.

The product's entire claim is: **every number is correct and traceable to a national guideline.** That principle, not the UI, drives the architecture. The canonical specs live in `docs/` — read them before changing behavior:

- `docs/prd.md` — product requirements (FR-/NFR- IDs)
- `docs/superpowers/specs/2026-08-10-supplement-recommendation-design.md` — the design spec (algorithm, worked examples §6.7)
- `docs/superpowers/plans/2026-08-10-supplement-engine-phase-0-1.md` — the executed Phase 0-1 TDD plan
- `docs/erd.md` — **canonical** DB schema; wins over PRD/PLAN summaries
- `docs/api.md` — HTTP API (Phase 2 endpoints specified in full)
- `docs/권한정책.md` — access control + trust boundaries (TB-1…TB-5)
- `docs/qa.md` — 142 numbered test cases (case IDs referenced from commits)
- `docs/wireframes/*.html` — screen structure and Korean copy
- `PLAN.md` — roadmap and locked decisions

## The one rule that shapes everything

**The LLM never produces a number.** The engine computes; the LLM only reads/writes natural language at four bounded call sites (OCR, parse, phrase follow-up questions, why-chat). Enforced structurally: `src/kdri/engine.py` and `lookup.py` have **no import path to any model API** (TB-1), and a test asserts `energy_ratio` never appears in `engine.py`.

## Architecture

```
backend/src/kdri/
  models.py   frozen dataclasses + TraceStep + NutrientResult
  loader.py   file → dataclass: load vendor CSVs, apply cited overrides,
              validate against published 2025 ranges, filter to adult scope,
              load curated limits/profiles/interactions/energy_ratios
  lookup.py   band lookup + 4-step form-scoped limit resolution
  engine.py   PURE — dual accounting, gap/headroom/recommend, status, priority
  db.py, api/, reports.py   Phase 2 (SQLite + FastAPI + the user_id accessor)
backend/data/
  vendor/     read-only, never hand-edited (47 codes, 1052 band rows, source PDF)
  curated/    authored by us, EVERY row carries a source (CI rejects blanks)
  demo/       illustrative diet baselines for screenshots only (KDRI_DEMO=1)
frontend/     Next.js App Router, Tailwind, Korean, "Paper Desk" skin
```

Data flows one way: seeded tables + curated files → **pure engine** → report + trace → persisted. The engine takes loaded tables as arguments, so it is fully testable with no database (Phase 0 has none).

### Load-bearing invariants (don't break these)

- **Adults 19+ only, sex required** — no `gender=ALL` band exists; sex cannot be defaulted (iron F 12 ≠ M 8).
- **Exactly 300 band rows** after filtering (30 nutrients × 5 bands × 2 sexes). Rectangular → the UL property test is exhaustive, not sampled.
- **Vendor CSVs are never edited.** Corrections go in `curated/overrides.csv`, each cited (magnesium M 15-18: 410→380).
- **One pill, two numbers** — a dose accounts separately toward the target and toward the limit when units/factors differ (folate 1.7× DFE; elemental %).
- **Limits are form-scoped**, resolved most-specific-first (niacin 니코틴산 35 vs 니코틴아미드 850; magnesium supplemental-only 350; folate µg vs µg DFE).
- **Missing diet baseline → `UNKNOWN`, no number** — guessing a baseline systematically over-recommends. Exception: a confirmed overshoot of a `supplemental_only` limit still reports `OVER` (safety leads; that basis excludes diet).
- **Reports are immutable.** `입력 수정` writes a new version with `parent_id`; there is no update endpoint.
- **Health-data reads go through one `user_id` accessor** (TB-3). A non-owned report returns **404, not 403**.

## Commands

```bash
# backend — run from backend/
cd backend && python -m pytest tests/ -q          # full suite
python -m pytest tests/test_golden.py -v          # the 5 hand-computed cases
python -m pytest tests/test_property.py -q         # 1200-combination UL invariant
# ad-hoc scripts need src on the path and utf-8 stdout on Windows (cp949 console):
PYTHONPATH=src PYTHONIOENCODING=utf-8 python -c "..."

# run the API (demo baselines make the report show numbers)
cd backend && KDRI_DEMO=1 uvicorn kdri.api.app:app --port 8000   # see api/ for real path

# frontend — run from frontend/
cd frontend && npm install && npm run dev
```

Windows note: the console is cp949 — printing Korean or `µ`/`α` characters crashes with `UnicodeEncodeError`. Set `PYTHONIOENCODING=utf-8`, or write to a utf-8 file and read it back.

## Working here

- **TDD.** Every arithmetic rule has a test; the golden and property tests encode numbers from the spec, not from the implementation — if they fail, the engine is wrong, not the test.
- Curated content changes only via reviewed files (TB-4); tests reject an uncited row, a `PROVISIONAL` baseline, an out-of-range `elemental_pct`, a missing profile, or an unknown `ul_basis`/`severity`.
- Diet baselines are currently `null` (source `none`) pending KNHANES sourcing — the real numbers are a pre-launch gate (PLAN.md §8 Q1). `backend/data/demo/` holds clearly-labelled illustrative values for screenshots only; the production path stays honest.
