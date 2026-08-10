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
| E | Report rendering (UI) | 15% | 3.5 | all 4 blocks, OVER-leads, UNKNOWN "—", trace expanders, AMDR no-trace, disclaimer, demo banner verified in browser; −0.5 for missing form/timing prose (S2) |
| F | Security & trust boundaries | 10% | 4.0 | TB-1 (no llm/energy_ratio in engine), TB-3 (single reports accessor), 404-not-403, FK pragma all confirmed by scan |
| G | Performance & ops | 5% | 4.0 | server-side report 6.8ms (budget 200ms); health band_rows=300; seed idempotent + aborts on assertion failure |

**Weighted overall: 3.89 / 4 (97%). No S1 findings — no wrong or unsafe number reaches a user.**

## Findings

**S1 (release-blocking): none.**

**S2 (real gaps, not wrong numbers):**
- FR-13 biomarker-driven priority is not wired: a flagged biomarker (e.g. low
  hemoglobin) does not lift iron in the ordering. The `Profile` engine type does
  not yet carry biomarkers. Refusals and status ordering are correct; only the
  biomarker nudge is absent.
- Report block 3 (추천) omits the "suggested form + why + timing" prose the
  wireframe shows (RP-10). The API contract exposes `recommend`/`limit`/
  `interactions`/`message_ko` but no `nutrient_timing` — that table is unseeded
  in Phase 1. Rendered faithfully from what the contract provides.

**S3 (cosmetic):**
- The intake wizard `<h1>` stays "기본 정보를 입력해 주세요" on step 2 (the step
  indicator and card heading do update).
- favicon 404 in the browser console.

## Integration bugs found during QA and already fixed
- Missing CORS blocked credentialed :3000→:8000 calls → `CORSMiddleware` added.
- Report envelope did not echo its profile → block 1 showed age·sex as "—" on
  reload → flattened profile echo added (report reproducible from its own row).

## Follow-ups for Phase 2.1 / later phases
1. Add `biomarkers` to the engine `Profile` and implement priority rank 2 (FR-13).
2. Author `nutrient_timing` (Phase 1 curated) and expose it so block 3 can show
   form choice rationale and timing.
3. Source the KNHANES diet baselines (pre-launch gate) to replace the demo overlay.
