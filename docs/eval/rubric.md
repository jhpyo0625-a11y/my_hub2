# Evaluation Rubric — 영양제 추천 엔진 (Phases 0-2)

Scores the **built system** against `docs/qa.md` (142 cases) and the specs. Scope
is Phases 0-2: engine, curated content, SQLite, FastAPI, and the Next.js intake +
report UI. Phases 3-7 features (free-text parse, OCR, follow-up questions,
why-chat, magic-link auth, history/versioning UI) are **N/A** here and excluded
from scoring — only VR-03 (immutability of a stored report) is in scope.

## How to score

Each criterion scored **0–4**:

| Score | Meaning |
|---|---|
| 4 | Fully correct, verified by a passing test or reproduced against the running system |
| 3 | Correct but unverified, or a trivial cosmetic gap |
| 2 | Partially implemented / a real gap that is not a wrong number |
| 1 | Present but wrong in a way that misleads |
| 0 | Missing, or produces a wrong/unsafe number (any S1 defect caps the section at 0) |

A section's score is the mean of its criteria, rounded to one decimal. The
**overall** score is the weighted mean of sections. **Any S1 finding (a wrong or
unsafe number reaching a user) is release-blocking regardless of the aggregate.**

Verification is evidence-based: run the command / reproduce the case, don't infer
from reading alone. Cite the case ID and how you verified it.

## Sections and weights

| # | Section | Weight | qa.md cases | How to verify |
|---|---|---|---|---|
| A | Data integrity & loading | 15% | DV-01…31 | `pytest tests/test_loader.py tests/test_ranges.py tests/test_curated.py` |
| B | Engine arithmetic | 25% | EN-01…75 | `pytest tests/test_engine.py test_lookup.py test_golden.py test_property.py`; recompute 2–3 golden cases by hand |
| C | Scope gates & refusals | 12% | SC-01…09 | POST out-of-scope profiles to the live API; assert `code` + no `results` |
| D | API contract & invariants | 18% | api.md §7 (1–8), RP data | Hit live API; assert 30 results, recommend≥0, recommend≤gap, trace coverage, GET==POST |
| E | Report rendering (UI) | 15% | RP-01…10, CF (render only) | Read `frontend/app/reports/[id]`; check 4 blocks, OVER-leads, UNKNOWN "—", trace expanders, AMDR no-trace, disclaimer, demo banner |
| F | Security & trust boundaries | 10% | SE-01…08, TB-1/3/5 | Code scan: no LLM import in engine; single reports accessor; 404-not-403; FK pragma; no health data in logs/errors |
| G | Performance & ops | 5% | PF-01…05 | Time a 30-nutrient report (<200ms); `/api/health` band_rows==300; reseed idempotency |

## Section criteria

### A — Data integrity (DV)
- A1 vendor load: 47 codes, 1052 rows; blank `ul_limit`→None not 0.0 (DV-01,02)
- A2 scope: exactly 30 nutrients, 300 rectangular rows, no <19, no (0,99), no ALL (DV-03…10)
- A3 override cited + applied; range check runs pre-filter and catches unpatched magnesium (DV-11…17)
- A4 curated citation gates: uncited/invalid rows raise; folate unit split; factor defaults (DV-21…30)

### B — Engine (EN) — highest weight, all S1
- B1 band lookup sex-specific + boundaries (EN-01…08)
- B2 form-scoped limit resolution, all 4 steps incl calcium within-nutrient UL (EN-10…17)
- B3 dual accounting: elemental %, folate 340/200 split, doses/day (EN-20…27)
- B4 round_down never rounds up; basis excludes/includes diet correctly; recommend≥0 (EN-30…39)
- B5 status + ordering: OVER first, UNKNOWN last, 30 results (EN-40…47)
- B6 the 5 golden cases pass with hand-computed numbers (EN-50…55)
- B7 exhaustive 1200-combination UL invariant (EN-60…64)
- B8 trace coverage: every reported number reachable; limit source recorded (EN-70…75)
- B9 (build decision) OVER surfaces on a supplemental-limit overshoot even with a null baseline

### C — Scope & refusals (SC)
- C1 age<19 → AGE_OUT_OF_SCOPE, no results (SC-01,02)
- C2 pregnancy/lactation → PREGNANCY_OUT_OF_SCOPE + referral, no results (SC-03,04)
- C3 sex omitted → SEX_REQUIRED, never defaults; sex="X" → 422 (SC-05,06)
- C4 unknown drug class → report succeeds, 평가되지 않음 on affected (SC-07)
- C5 every refusal carries code + Korean message + reason; never a zero-filled report (SC-08,09)

### D — API contract & invariants
- D1 results always length 30 (§7.1)
- D2 recommend≥0 and recommend≤gap always (§7.2,3)
- D3 limit non-null → recommend≤max(0,headroom); limit null → recommend==round_down(gap) (§7.4,5)
- D4 every non-null number reachable from a trace step (§7.6)
- D5 no LLM-generated text in results (§7.7)
- D6 GET after POST byte-identical results = immutability (§7.8, VR-03)
- D7 reference returns 30 nutrients + forms + drug_classes + energy_ratios
- D8 message_ko is deterministic (no LLM) and matches status/numbers

### E — Report rendering (RP)
- E1 four blocks present and ordered (RP-01)
- E2 OVER → reduction instruction at top, not a dose (RP-02)
- E3 UNKNOWN → target+current shown, no recommendation, reason stated (RP-03)
- E4 weight → "결과 미반영" note (RP-04)
- E5 block 4 AMDR labelled reference, has NO trace (RP-05,06)
- E6 trace expanders on blocks 2–3 numbers (RP-07)
- E7 disclaimer on report; interaction flag with severity + spacing; demo banner when demo_data (RP-08,09)
- E8 accessibility: labels, focus-visible, aria-pressed segments, prefers-reduced-motion

### F — Security & trust boundaries
- F1 TB-1: engine.py/lookup.py have no `llm` import; `energy_ratio` absent from engine (EN-74,75)
- F2 TB-3: one accessor owns reports/chat queries; no ad-hoc SELECT elsewhere (SE-02)
- F3 non-owned report → 404 not 403 (SE-01)
- F4 SQLite `PRAGMA foreign_keys=ON` per connection (SE-07)
- F5 no report contents in logs; INTERNAL error carries no health data (SE-03,04)
- F6 cookie flags HTTP-only/SameSite; no name/주민번호 stored (SE-06,08)

### G — Performance & ops
- G1 full 30-nutrient report < 200ms server-side (PF-01)
- G2 /api/health band_rows==300, seed_assertions passed (PF-03)
- G3 seed assertion failure aborts startup; reseed idempotent (PF-04,05)

## Deliverable per eval agent

For each assigned section: a score per criterion (0–4) with the evidence
(command run + observed result, or file:line), the section mean, and a
prioritized findings list (S1/S2/S3). Report only what you verified. Do not fix
anything — scoring only.
