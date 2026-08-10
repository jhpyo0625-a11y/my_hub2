# 영양제 추천 엔진 — MVP Plan

An AI supplement recommendation service for Korean adults. The user supplies basic accurate facts — age, sex, what they already take, what they're prescribed — and the system returns an evidence-based answer to *what should I take, how much, and when*, computed against the 2025 한국인 영양소 섭취기준 (KDRI).

The differentiator is not the conversation. It is that **every number is correct and traceable to a national guideline**.

### Key architecture facts

- **FastAPI + SQLAlchemy** backend, **Next.js App Router** frontend, Korean-only output.
- **KDRI 2025 vendor CSVs are the source of truth** for every dose number. Curated files layer on top; every curated row carries a citation.
- **The LLM never produces a number.** It parses input and phrases output at exactly four call sites. The engine computes.
- **The engine is pure** — no I/O, no database, no network. It takes loaded tables as arguments and returns a result plus a trace.

**Status:** spec and Phase 0-1 implementation plan committed on `spec/supplement-recommendation-mvp`. No application code yet.

---

## 1. Key Decisions (locked in)

| Decision | Choice |
|---|---|
| **Stack** | FastAPI + SQLAlchemy backend, Next.js App Router frontend, Korean-only output |
| **Persistence** | **None in Phase 0-1** — in-memory frozen dataclasses. **SQLite from Phase 2.** Schema kept Postgres-portable |
| **Source of truth** | KDRI 2025 vendor CSVs, read-only and never hand-edited. Curated files layer on top |
| **LLM boundary** | Never produces a number. Four call sites only: OCR, parse, phrase questions, why-chat |
| **OCR** | Naver **CLOVA OCR** extracts Korean label text; **Claude** parses it into structured intake |
| **Scope** | Adults 19+, 30 nutrients (14 vitamins + 15 minerals + EPA/DHA) |
| **Excluded** | Pregnancy, lactation, under-19, therapeutic dosing above RI, macronutrient recommendations |
| **Target rule** | `target = ri_base`; UL is a hard cap; `gap = target − diet − supplements` |
| **Upper limits** | Form-scoped via `nutrient_limits` — magnesium supplemental-only, niacin 35 vs 850, folate µg vs µg DFE |
| **Diet baseline** | One KNHANES-sourced constant per nutrient. Unsourced → `UNKNOWN`, no number emitted |
| **Biomarkers** | Prioritize and contextualize only. Never move the target |
| **Medications** | Curated deterministic interaction table. Anything outside it returns 평가되지 않음 |
| **Data validation** | 30 in scope; **28 match the published 2025 ranges as shipped**; magnesium corrected by a cited override; `epa_dha` allowlisted with a documented reason |
| **Testing** | TDD throughout. Exhaustive 300-row UL property test, 5 golden cases, published-range fixture, trace completeness |
| **Auth** | Email magic link, no passwords |
| **Health data** | Every row scoped to `user_id` through a single accessor. App-layer enforcement, limits documented |
| **Content authoring** | Curated YAML/CSV edited by a nutrition reviewer via git PR. Tests reject uncited rows. No admin UI |
| **Report model** | Immutable versions. `입력 수정` recomputes into a new version with `parent_id` |
| **Why-chat** | Read-only. Answers strictly from the stored trace, refuses to produce new dosing |

### Data validation rules

The 2025 press release (붙임3) publishes an RNI/AI range per nutrient. The comparison rule is not "all rows" — the published range covers each nutrient's **own reference type**:

- `has_rni = true` → range spans RNI bands only; infant month bands `(0,5)` and `(6,11)` are excluded
- `has_rni = false` → AI nutrient; range spans every band including infants
- Pregnancy rows `(0,99)` are excluded either way

| Outcome | Count | Handling |
|---|---|---|
| Match the published range exactly | **28 / 30** | — |
| Magnesium `M 15-18 = 410` | 1 | 2020 value surviving in a 2025 file. Corrected to 380 by a cited `overrides.csv` row |
| `epa_dha` | 1 | Allowlisted. Published endpoints (100, 300) come from infant and pregnancy life stages our data lacks or drops; 150–250 is correct |

The check runs on the **full 1052 rows before scope filtering**. Filtering to adults first would have hidden the magnesium defect — a check that only sees what you already trust is worth nothing.

---

## 2. User Roles

- **사용자 (End user)** — a Korean adult 19+. Supplies age, sex, current supplements, medications, and optionally health-checkup biomarkers. Reads a report, answers follow-up questions, asks why. Owns their reports; sees only their own.
- **Nutrition reviewer (content curator)** — authors and cites the curated layer: 30 diet baselines from KNHANES, supplement forms with elemental percentages, timing guidance, and the drug-interaction table. Works in YAML/CSV through git PRs; the test suite rejects any uncited row. Not a system login.
- **The engine** — a deterministic actor, not a person. Owns every number. Emits a trace for each one.
- **The LLM** — a bounded actor. Reads and writes natural language at four call sites, never authors a dose, a limit, or an interaction.
- **Pharmacist / clinician** — explicitly *not* a system actor. The referral target when input falls outside scope (pregnancy, under-19, an unevaluated drug class) or when a biomarker is flagged.

### Data flow

```
사용자
  │ ① age, sex, goals                    (age + sex required; everything else optional)
  ▼
[ Intake Wizard ]
  │
  ├─ ② photo ──▶ [LLM: CLOVA OCR] ──┐
  │                                  ├──▶ [LLM: Claude parse] ──▶ ┌─────────────────┐
  └─ ② text ────────────────────────┘                             │ Confirm Screen  │
                                                                  │ user approves   │
                                                                  └────────┬────────┘
                                                    ── trust boundary ─────┼──────────
                                                                           ▼
                                                                  ┌─────────────────┐
                          ③ ranked gaps  ◀──────────────────────  │  ENGINE (pure)  │
                                │                                 └────────┬────────┘
                                ▼                                          │ ④ Report + Trace
                    [LLM: phrase questions]                                ▼
                                │                                 ┌─────────────────┐
                                └──▶ 사용자 answers ──▶ re-run ──▶│ Report (4 blocks)│
                                                                  └────────┬────────┘
                                                                           │
                                             [LLM: why-chat] ◀─── trace ───┘
                                             read-only, refuses new dosing
```

Both input paths converge on **one** confirm screen. That screen is the trust boundary: nothing unstructured reaches the engine without a human approving it.

---

## 3. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  frontend/            Next.js App Router · Tailwind · Korean     │
│  intake · confirm · report · history · chat                      │
└───────────────────────────────┬──────────────────────────────────┘
                                │ HTTP / JSON
┌───────────────────────────────▼──────────────────────────────────┐
│  backend/src/kdri/api/        FastAPI routes                     │
│  reports · chat · auth                                           │
├──────────────────────────────────────────────────────────────────┤
│  backend/src/kdri/llm/        ◀── the LLM lives ONLY here        │
│  ocr · parse · questions · chat                                  │
├──────────────────────────────────────────────────────────────────┤
│  backend/src/kdri/            PURE — no I/O, no DB, no network   │
│  engine.py · lookup.py · models.py                               │
│  ▲ no import path to llm/ or api/ — enforced by test             │
├──────────────────────────────────────────────────────────────────┤
│  backend/src/kdri/loader.py   file → dataclass, with assertions  │
├──────────────────────────────────────────────────────────────────┤
│  backend/data/                                                   │
│  vendor/   read-only, never hand-edited                          │
│  curated/  authored by us, every row cited                       │
└──────────────────────────────────────────────────────────────────┘
```

### Module boundary

The one rule that shapes everything: **`engine/` has no import path to `llm/`.** A test reads the engine source and asserts it. If the engine cannot reach a model API, no model can quietly become the origin of a dose.

The engine takes loaded tables as arguments rather than reading them, which is why Phase 0 needs no database to be fully testable.

### File layout

```
backend/
  pyproject.toml
  data/
    vendor/                        read-only
      nutrient_codes.csv           47 rows
      kdri_standards.csv           1052 rows → 300 after filtering
      2025_KDRI_보도자료.pdf        source for the range fixture
    curated/                       every row cited
      overrides.csv                vendor value corrections
      nutrient_limits.csv          form-scoped upper limits
      nutrient_profiles.yaml       diet baselines, forms, conversion factors
      interactions.csv             nutrient × drug class
      energy_ratios.csv            AMDR, reference only
  src/kdri/
    models.py                      frozen dataclasses + TraceStep
    loader.py                      load, patch, validate, filter, assert
    lookup.py                      band lookup + 4-step limit resolution
    engine.py                      accounting, computation, status, priority
    db.py                          Phase 2
    api/                           Phase 2
    llm/                           Phase 3+
  tests/
    fixtures/kdri_2025_ranges.csv
    test_loader · test_ranges · test_lookup · test_engine
    test_golden · test_property · test_curated
frontend/                          Phase 2
```

---

## 4. Data Model (SQLite → Postgres path)

No database exists in Phase 0-1. The tables below are seeded from files in Phase 2. Types are kept portable so a move to Postgres is a driver swap, not a rewrite.

```
-- ── seeded from files at startup, read-only at runtime ──────────

nutrients
  nutrient_code (pk), nutrient_ko, group_name
  target_unit, ul_unit              -- differ only for folate (µg DFE vs µg)
  synonyms_ko_label                 -- pipe-delimited; powers parser matching
  has_rni, has_ai, has_ul

kdri_bands
  nutrient_code, sex ('M'|'F'), age_min, age_max
  ri_base, ul_limit (nullable)
  -- exactly 300 rows: 30 nutrients × 5 adult bands × 2 sexes
  -- no gender='ALL' row exists for adults, so sex has no fallback

nutrient_limits                     -- form-scoped upper limits
  nutrient_code
  applies_to_form (nullable)        -- null = all supplemental forms
  age_min, age_max, sex
  ul_value, ul_unit
  ul_basis ('total_intake'|'supplemental_only')
  source (required)

nutrient_forms
  nutrient_code, name_ko
  elemental_pct                     -- 산화마그네슘 0.603, 비스글리시네이트 0.141
  target_factor, ul_factor          -- default 1.0; folate 합성 엽산 is 1.7 / 1.0
  absorption, gi_note, source

nutrient_timing
  nutrient_code, when, with_food, split_dose_above, rationale_ko, source

interactions
  nutrient_code, drug_class, drug_examples_ko
  effect, action, severity ('low'|'medium'|'high'|'critical'), source

energy_ratios                       -- AMDR; the engine never reads this table
  macronutrient, age_min, age_max, pct_min, pct_max, source, changed_2025

-- ── user data, written at runtime (Phase 2+) ────────────────────

users
  id (pk), email (unique), created_at

magic_links
  token (pk), user_id, expires_at, used_at

reports
  id (pk), user_id, version, parent_id (nullable, self-ref)
  profile_json                      -- full input snapshot
  result_json                       -- per-nutrient results
  trace_json                        -- every rule that fired
  created_at

chat_messages
  id (pk), report_id, role ('user'|'assistant'), content, created_at
```

### Why reports are immutable

A report stores its own `profile_json`, so it is reproducible from its own row without joining anything that may since have changed. `입력 수정` never mutates: it prefills the wizard from the snapshot, recomputes, and writes **v2 with `parent_id = v1`**. History shows revision chains, and the why-chat binds to one version — so "why did you recommend this" is always answerable, because the exact trace that produced that answer is stored beside it.

This is what makes a read-only chat acceptable. The user changes a recommendation by changing inputs and re-running the engine, never by arguing with the model.

### Data sensitivity

- **Stored:** age, sex, optional weight, supplement list, medication *classes*, biomarker values, report history.
- **Never stored:** name, 주민등록번호, full medical records, or the raw checkup document after extraction.
- Every `reports` and `chat_messages` read goes through **one accessor keyed on `user_id`**. No ad-hoc queries against those tables.
- Deleting a user cascades to their reports and chat messages.
- **Stated limit:** this is app-layer enforcement, not database-enforced. A bug in the accessor is a cross-user leak of health data. Postgres row-level security is the upgrade path, and it is the main reason the schema is kept portable.

---

## 5. Core Pipelines

### A. Intake → Confirm

Both paths converge before anything is computed.

| Step | Actor | Output |
|---|---|---|
| Photo upload | 사용자 | image |
| Text extraction | **CLOVA OCR** | raw Korean label text |
| — or manual entry | 사용자 | raw text |
| Structuring | **Claude** | `list[SupplementIntake]`, validated against `synonyms_ko_label` |
| **Confirm screen** | 사용자 | approved intake list → engine |

Anything the parser cannot map to a `nutrient_code` surfaces on the confirm screen as unresolved. It is never silently dropped, and it never reaches the engine unapproved.

### B. Engine calculation

```
band          = lookup(sex, age)                    exact match, asserted non-null
target        = band.ri_base                        after overrides, in target_unit
diet          = target × nutrient.diet_baseline_pct

toward_target = Σ(dose × elemental_pct × target_factor × doses_per_day)
toward_limit  = Σ(dose × elemental_pct × ul_factor     × doses_per_day)

gap           = max(0, target − diet − toward_target)
limit         = resolve_limit(nutrient, declared_forms, age, sex)

if limit is None:                    headroom = None
elif limit.basis == supplemental_only: headroom = limit.value − toward_limit
else:                                  headroom = limit.value − diet − toward_limit

recommend     = gap if headroom is None else min(gap, headroom)
recommend     = round_down(max(0, recommend), 2 sig figs)
```

**One pill produces two numbers.** A 400 µg folic acid tablet contributes 680 µg DFE toward the target but 400 µg toward the limit. Collapsing them under-counts folate intake by ~70%.

**Limit resolution is form-scoped**, most specific first:

1. a `nutrient_limits` row matching the user's declared form — 니코틴아미드 → 850 mg NE
2. a nutrient-wide row — magnesium → 350 mg, supplemental only
3. the vendor band's `ul_limit`, always total-intake basis
4. no limit — `recommend` is capped by `gap` alone, so absence of a ceiling never means an unbounded dose

**Status:** `OVER` when headroom < 0 · `DEFICIT` when gap > 0 · `ADEQUATE` · `UNKNOWN` when no band or no sourced baseline. `OVER` leads the report — over-supplementing is the more common real-world failure than deficiency.

**Follow-up questions come from sensitivity analysis, not from the model.** The engine re-runs with each missing field pinned to its plausible min and max, ranks fields by how far any recommendation swings, and hands the top 3 to the LLM to phrase. ~360 arithmetic runs, sub-millisecond. The system structurally cannot ask for data that would not change its answer.

### C. LLM boundaries

| # | Call site | Input | Output | Hard constraint |
|---|---|---|---|---|
| 1 | OCR | bottle photo | raw text | CLOVA; extraction only, no interpretation |
| 2 | Parse | text | structured intake | validated against synonyms, **user confirms** |
| 3 | Phrase follow-ups | engine's ranked gap list | Korean questions | cannot invent a question off-list |
| 4 | Why-chat | trace JSON + question | Korean explanation | read-only, refuses new dosing |

The LLM never: picks a dose, sets a target, decides an interaction, or resolves an upper limit.

---

## 6. Feature Breakdown by Area

### A. Intake wizard (`/intake`)

- Age and sex are **required** — no `gender=ALL` band exists for adults, so the data cannot answer without them. The form explains why rather than just marking them required.
- Everything else optional. Skipped fields fall back to national defaults.
- Weight is collected and stored but **affects nothing**: `is_weight_scaled` is `false` on all 1052 KDRI rows. The UI says so instead of implying precision it doesn't have.
- Under-19, pregnancy, or lactation → refusal with a stated reason and a clinician referral. No numbers.
- Optional biomarker entry (hemoglobin, ferritin, vitamin D) — flags priority, never changes a target.

### B. Confirm screen (`/intake/confirm`)

- One screen for both OCR and manual paths.
- Parsed rows shown as an editable table: nutrient, form, dose, unit, doses/day.
- Unresolved items flagged, never dropped.
- Ambiguous labels ask which reading applies — "마그네슘 400mg" as elemental vs compound changes the answer by 2.5×.

### C. Report (`/reports/[id]`)

Four blocks:

1. **입력 요약** — profile as parsed, with `입력 수정`
2. **현재 상태 분석** — per nutrient: target, from diet, from supplements, gap, status. `OVER` and biomarker-flagged lead
3. **추천** — elemental amount, suggested form *and why that form*, timing, interaction flags, citations
4. **참고: 2025 에너지 적정비율** — AMDR (탄수화물 50-65%, 단백질 10-20%, 지방 15-30%) as reference only

Every number in blocks 2 and 3 expands to its trace step. Block 4 has no trace because nothing was computed — that asymmetry is deliberate and visible.

### D. Why-chat and history (`/history`)

- Chat bound to one report version, answering only from its stored trace.
- `입력 수정` → recompute → new version with `parent_id`. Nothing mutates.
- History lists revision chains, so a user can see how a recommendation moved when they corrected an input.

### E. Curated content workflow (no UI)

- Nutrition reviewer edits `nutrient_profiles.yaml`, `interactions.csv`, `nutrient_limits.csv`, `overrides.csv` and opens a PR.
- CI rejects: an uncited row, a `PROVISIONAL` baseline, an out-of-range `elemental_pct`, a missing profile for an in-scope nutrient, a generic placeholder source.
- Every content change is a reviewable diff with history — which is what an evidence claim actually requires. An admin CRUD panel would destroy that property.

---

## 7. Build Phases

### Phase 0 — Engine (Tasks 1-12)

No UI, no LLM, no database. Ships a testable dose calculator with nothing attached, so wrong arithmetic is found before anything is built on top of it.

| # | Task | Green when |
|---|---|---|
| 1 | Scaffold + vendor relocation | 47 codes, 1052 rows, PDF present |
| 2 | Domain models + vendor loading | flags, synonyms, blanks → `None` |
| 3 | Cited vendor overrides | magnesium 15-18 → 380; uncited row raises |
| 4 | 2025 published-range fixture | 0 deviations patched; magnesium detected unpatched |
| 5 | Scope filter + seed assertions | exactly 300 rectangular rows |
| 6 | Curated limits + profiles | niacin two limits; folate split units |
| 7 | Band lookup + limit resolution | all 4 resolution steps; sex-specific targets |
| 8 | Dual accounting + core computation | 340 DFE vs 200 µg from one tablet |
| 9 | Five golden cases | the traps in §5B, hand-computed |
| 10 | Exhaustive UL property test | 300 rows × 4 intake levels = 1200 combinations |
| 11 | Priority ordering + full report | `OVER` first, `UNKNOWN` last, under-19 refused |
| 12 | Trace completeness | every reported number reachable from a trace step |

### Phase 1 — Curated content (Tasks 13-14)

| # | Task | Green when |
|---|---|---|
| 13 | 30 cited diet baselines + forms | no `PROVISIONAL`; unsourced → explicit `none` |
| 14 | Interaction table + AMDR reference | every row cites a named reference; engine never imports `energy_ratios` |

### Phase 2 — API and report page

SQLite persistence reusing `loader.py` unchanged · `POST /reports`, `GET /reports/{id}` · intake wizard · report page with expandable traces.

### Phase 3 — Manual entry and confirm screen

Claude parser validated against `synonyms_ko_label` · the confirm screen as trust boundary.

### Phase 4 — OCR

CLOVA OCR behind an interface, converging on Phase 3's parser and confirm screen unchanged.

### Phase 5 — Follow-up questions

Sensitivity analysis in `sensitivity.py` · LLM phrasing bounded to the engine's ranked list.

### Phase 6 — Why-chat

Trace serialization · read-only chat endpoint bound to one report version.

### Phase 7 — Auth, history, versioning

Magic link issue and verify · `parent_id` version chains · history UI.

---

## 8. Open Questions

1. **KNHANES sourcing for 30 diet baselines** — which survey year and table per nutrient. Blocks Task 13, and it is the single weakest number in the product: one national constant means a vegan and a daily steak eater get the same iron baseline.
2. **Full KDRI standards volume** — the press release validates our data but cannot populate it. A stale value sitting *inside* its published range passes the fixture undetected. Re-sourcing from kns.or.kr is a **pre-launch gate**, not a Phase 0 blocker.
3. **Interaction table authorship** — who reviews it, and against which reference. Currently the highest-liability hand-authored table in the repo.
4. **CLOVA OCR accuracy on curved bottle labels** — measure against real photos in Phase 4 before committing. The OCR interface exists so the implementation can be swapped.
5. **Folate 1.7× vs 2.0×** — fixed at 1.7 (with food). Revisit if the with-meal assumption proves wrong in practice.
6. **Diet baseline questionnaire** — at what point does the flat constant stop being defensible and the 5-8 question dietary survey become necessary.
7. **Hosting and deployment target** — not yet decided; affects nothing structurally.
8. **Regulatory posture** — how the service must present itself under Korean 건강기능식품 and medical-advice rules. Needs a legal read before launch, and it may constrain the wording of block 3.
9. **Pregnancy, lactation, pediatric expansion** — needs a normalized `life_stage` column, sourced lactation deltas, and a resolution of the `F(0,99)` encoding inconsistency (most rows are deltas, `epa_dha` appears to be an absolute).

---

## 9. What "done" looks like

A Korean adult opens the site, enters their age and sex, and photographs the three supplement bottles on their desk. The labels are read, parsed, and shown back to them to confirm — including the one the parser wasn't sure about. The system asks two follow-up questions, and only two, because those are the only missing facts that would move a number.

The report opens with a warning: the 600 mg magnesium oxide they've been taking daily is 362 mg of elemental magnesium, past the 350 mg supplemental upper limit, and they should cut back. Below that, their folate is fine — the 200 µg tablet is really 340 µg DFE — and their vitamin D is 8 µg short, best taken with dinner, as D3. Their levothyroxine is flagged against the calcium, with a four-hour spacing instruction.

They tap "왜 이렇게 나왔나요?" on the magnesium line and get the actual arithmetic: the band that matched, the elemental percentage, the limit that applied and why it excludes food. They realize they forgot a multivitamin, hit `입력 수정`, and get v2 in seconds — with v1 still in their history to compare against.

Nothing in that report was written by a language model. Every number came from a pure function reading a cited table, and every one of them can be traced back to the line in the 2025 한국인 영양소 섭취기준 that produced it.
