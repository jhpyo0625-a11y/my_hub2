# Evaluation Results — Phases 0-2

Scored against [rubric.md](rubric.md). Verification was hands-on: 75 automated
tests, live-API reproduction, full Playwright UI walkthrough, and code scans.
The three parallel eval agents were interrupted by a session limit before
reporting, so the maintainer completed the scoring from the same evidence.

## Scorecard

| # | Section | Weight | Score | Basis |
|---|---|---|---|---|
| A | Data integrity & loading | 15% | 4.0 | `test_loader/test_ranges/test_curated` green; range fixture catches unpatched magnesium |
| B | Engine arithmetic | 25% | 4.0 | 5 golden cases + 1200-combo UL property test green; mg 361.8 / folate 340 DFE recomputed by hand; OVER-on-null-baseline reproduced |
| C | Scope gates & refusals | 12% | 3.7 | age/pregnancy/sex refusals reproduced live (correct code + referral + no results); SC-06/07 covered by tests only |
| D | API contract & invariants | 18% | 4.0 | 30 results, recommend≥0/≤gap, trace coverage, GET==POST immutability all asserted; reference=30; message_ko deterministic (no LLM) |
| E | Report rendering (UI) | 15% | 3.9 | all 4 blocks, OVER-leads, UNKNOWN "—", trace expanders, AMDR no-trace, disclaimer, demo banner verified in browser; block-3 form/timing prose now rendered from cited `guidance` (magnesium/iron authored) |
| F | Security & trust boundaries | 10% | 4.0 | TB-1 (no llm/energy_ratio in engine), TB-3 (single reports accessor), 404-not-403, FK pragma all confirmed by scan |
| G | Performance & ops | 5% | 4.0 | server-side report 6.8ms (budget 200ms); health band_rows=300; seed idempotent + aborts on assertion failure |

**Weighted overall: 3.95 / 4 (99%). No S1 findings — no wrong or unsafe number reaches a user.**

## Findings

**S1 (release-blocking): none.**

**S2 (real gaps, not wrong numbers):**
- ~~FR-13 biomarker-driven priority is not wired.~~ **RESOLVED.** Cited
  `biomarkers.csv` (hemoglobin/ferritin→iron, 25(OH)D→vitamin D) drives a
  priority tier directly under OVER; a below-range value flags the nutrient and
  adds a "target unchanged, see a doctor" note. Verified end-to-end (engine
  tests + live UI): low hemoglobin lifts iron to the top with its dosing numbers
  untouched. 80 tests green.
- ~~Report block 3 (추천) omits the "suggested form + why + timing" prose the
  wireframe shows (RP-10).~~ **RESOLVED.** A cited `guidance` block on the
  nutrient profile (recommended form / reason / timing) now serializes as
  `results[].guidance` and renders as 권장 형태 / 이유 / 복용 시점 rows in block 3.
  Qualitative only — the engine is untouched, so no number moves and the UL
  property test is unaffected. Authored for magnesium and iron (the wireframe's
  worked examples), each cited to a real paper; other nutrients render no
  guidance block until their advice is authored and cited — same honesty bar as
  the null diet baselines.

**S3 (cosmetic):**
- ~~The intake wizard `<h1>` stays "기본 정보를 입력해 주세요" on step 2.~~ **Fixed** —
  the `<h1>` and lede now switch with the step.
- ~~favicon 404 in the browser console.~~ **Fixed** — `app/icon.svg` (Paper Desk
  capsule) added.

## Integration bugs found during QA and already fixed
- Missing CORS blocked credentialed :3000→:8000 calls → `CORSMiddleware` added.
- Report envelope did not echo its profile → block 1 showed age·sex as "—" on
  reload → flattened profile echo added (report reproducible from its own row).

## Follow-ups for Phase 2.1 / later phases
1. ~~Add `biomarkers` to the engine `Profile` and implement priority rank 2 (FR-13).~~ **Done.**
2. ~~Author `nutrient_timing` (Phase 1 curated) and expose it so block 3 can show
   form choice rationale and timing.~~ **Done** as a cited `guidance` block on the
   nutrient profile (magnesium, iron authored; remaining nutrients pending
   pharmacist-reviewed citations).
3. Source the KNHANES diet baselines (pre-launch gate) to replace the demo overlay.
5. ~~Build the history screen (S-09).~~ **Done** — `GET /api/reports` (session-scoped
   via the TB-3 accessor) + `/history` renders the immutable version chain.
4. Add a `biomarkers` seeded table to `erd.md`/`db.py` (currently the engine reads
   the cited refs from files only, consistent with limits/profiles).
