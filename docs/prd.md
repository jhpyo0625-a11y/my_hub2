# PRD — 영양제 추천 엔진

**Status:** approved for Phase 0-1 execution
**Owner:** jhpyo
**Last updated:** 2026-08-10
**Related:** [PLAN.md](../PLAN.md) · [design spec](superpowers/specs/2026-08-10-supplement-recommendation-design.md) · [Phase 0-1 plan](superpowers/plans/2026-08-10-supplement-engine-phase-0-1.md)

---

## 1. Overview

An AI supplement recommendation service for Korean adults. The user supplies basic accurate facts. The system computes an evidence-based answer to *what should I take, how much, and when*, against the 2025 한국인 영양소 섭취기준 (KDRI).

The product's claim is not that it converses well. It is that **every number is correct and traceable to a national guideline**. That claim drives every requirement below.

---

## 2. Problem

A consumer who wants better sleep and hears "magnesium" faces a research problem, not a shopping problem:

- **Which form?** 산화마그네슘, 구연산마그네슘, 비스글리시네이트 — different elemental content, absorption, and GI tolerance.
- **How much?** The label says 400 mg. Bisglycinate at 400 mg delivers **56 mg** of elemental magnesium. Oxide at 400 mg delivers **241 mg**. The label number is not the dose.
- **On top of what?** Their multivitamin already contains magnesium. Their diet supplies more.
- **Is it safe with my medication?** Magnesium chelates quinolone antibiotics.
- **When?** Evening, with food, split above 400 mg.

No single source answers all five for one specific person. The user is expected to become an amateur nutritionist or guess.

**The failure mode is bidirectional.** Under-supplementing wastes money. Over-supplementing causes harm — and a 600 mg 산화마그네슘 tablet, sold on the Korean market, puts a daily user past the supplemental upper limit with no way to know.

---

## 3. Target users

**Primary — the informed consumer.** Korean adult 19+, already takes one to five supplements, bought them on recommendation or marketing rather than calculation. Can read a label but cannot convert it. Wants a number and a reason.

**Secondary — the checkup follow-up.** Received a 건강검진 result with a flagged value (low hemoglobin, low vitamin D) and wants to know what to do about it nutritionally, understanding this is not treatment.

**Explicitly not served in MVP:** pregnant or lactating users, under-19, anyone seeking therapeutic dosing for a diagnosed condition. Each gets a stated refusal and a clinician referral, never a number. See §7.

---

## 4. Goals and non-goals

### Goals

| # | Goal | Measured by |
|---|---|---|
| G1 | Answer "how much" correctly for 30 nutrients | 1200-combination UL property test passes |
| G2 | Convert label doses to elemental amounts | Golden cases A, B pass |
| G3 | Subtract what the user already takes and eats | `gap = target − diet − supplements` traced |
| G4 | Flag over-supplementation, not only deficiency | `OVER` status leads the report |
| G5 | Make every number explainable after the fact | 100% trace coverage test |
| G6 | Ask only for information that changes an answer | Follow-ups derived from sensitivity analysis |

### Non-goals

| Non-goal | Why |
|---|---|
| Diagnose or treat | Nutrition guidance, not clinical care. Biomarkers prioritize, never re-target |
| Recommend brands or products | No product catalog dataset exists |
| Log food intake | Out of scope; the diet baseline is a national constant instead |
| Compute the user's macro ratio | An AMDR needs actual energy intake. Shown as reference only |
| Serve pregnancy, lactation, pediatric | Highest-liability populations; source data is incomplete for them |
| Chat that can change a dose | The chat is read-only. Inputs change doses, arguments do not |

---

## 5. Functional requirements

Referenced by [기능명세서.md](기능명세서.md) and [qa.md](qa.md).

### Intake

| ID | Requirement | Phase |
|---|---|---|
| **FR-1** | Collect age and sex as **required**; weight, goals as optional. Explain why sex is required | 2 |
| **FR-2** | Accept current supplements as free text | 3 |
| **FR-3** | Accept a bottle photo and extract label text | 4 |
| **FR-4** | Show every parsed intake on a confirm screen for user approval before any computation | 3 |
| **FR-5** | Accept current medications as drug classes | 2 |
| **FR-6** | Accept optional health-checkup biomarker values | 2 |
| **FR-15** | Ask at most 3 follow-up questions, chosen by engine sensitivity analysis | 5 |

### Engine

| ID | Requirement | Phase |
|---|---|---|
| **FR-7** | Compute `target = ri_base` from an exact (sex, age-band) match | 0 |
| **FR-8** | Never recommend a dose that pushes intake past an applicable upper limit | 0 |
| **FR-9** | Resolve upper limits through the declared supplement form, most specific first | 0 |
| **FR-10** | Account separately toward target and toward limit when units differ | 0 |
| **FR-11** | Subtract a cited national diet baseline before computing the gap | 0 |
| **FR-12** | Classify each nutrient `DEFICIT` / `ADEQUATE` / `OVER` / `UNKNOWN` | 0 |
| **FR-13** | Order results safety-first: `OVER`, biomarker-flagged, largest deficit, adequate, unknown | 0 |
| **FR-14** | Emit a trace step for every number that reaches the report | 0 |
| **FR-24** | Reject uncited, provisional, or incomplete curated content at load | 0-1 |

### Output

| ID | Requirement | Phase |
|---|---|---|
| **FR-16** | Render a report in four blocks: 입력 요약, 현재 상태 분석, 추천, 참고 | 2 |
| **FR-17** | Show 2025 AMDR ranges as reference, explicitly not as an assessment | 2 |
| **FR-18** | Flag nutrient-drug interactions from the curated table; return 평가되지 않음 outside it | 2 |
| **FR-19** | Answer "why" strictly from the stored trace; refuse to produce new dosing | 6 |

### Account and history

| ID | Requirement | Phase |
|---|---|---|
| **FR-20** | Store reports as immutable versions; 입력 수정 creates v+1 with `parent_id` | 7 |
| **FR-21** | List a user's report history as revision chains | 7 |
| **FR-22** | Authenticate by email magic link; no passwords | 7 |
| **FR-23** | Refuse out-of-scope profiles with a stated reason and a referral | 0 |

---

## 6. Non-functional requirements

| ID | Requirement | Rationale |
|---|---|---|
| **NFR-1** | The engine module has no import path to any model API, enforced by test | The LLM must never be able to originate a number |
| **NFR-2** | The engine is pure — no I/O, no DB, no network | Makes exhaustive testing possible |
| **NFR-3** | Every curated value carries a source string; CI rejects blanks and placeholders | An evidence claim requires evidence |
| **NFR-4** | Vendor CSVs are never hand-edited; corrections live in `overrides.csv` | Keeps the national-guideline / our-judgment line greppable |
| **NFR-5** | A full report computes in under 200 ms server-side, excluding LLM calls | Sensitivity analysis runs ~360 engine passes per request |
| **NFR-6** | All user-facing copy in Korean | Source of truth is a Korean national guideline |
| **NFR-7** | Reports are reproducible from their own row | `profile_json` is a snapshot, not a live join |
| **NFR-8** | Health data reads scope through a single `user_id` accessor | See [권한정책.md](권한정책.md) |

---

## 7. Scope boundaries and refusals

The system declines rather than guesses. Every refusal states its reason.

| Condition | Behavior |
|---|---|
| Age < 19 | Refuse. Pediatric dosing is out of scope; source age bands collide below 19 |
| Pregnancy or lactation declared | Refuse, refer to 산부인과. Lactation deltas are absent from source data |
| No band row for a nutrient | `UNKNOWN`, no number |
| No sourced diet baseline | `UNKNOWN`, no number. Guessing a baseline systematically over-recommends |
| Intake already exceeds an upper limit | `OVER`, reduction guidance, leads the report |
| Drug class outside the interaction table | 평가되지 않음 — 약사와 상담하세요 |
| Every report | Non-diagnostic disclaimer |

---

## 8. Success criteria

No business targets are set. These are the design-derived criteria that determine whether the thing works.

| Criterion | Target | Phase |
|---|---|---|
| UL invariant holds across every adult band | 1200/1200 combinations | 0 |
| Golden arithmetic cases | 5/5 hand-computed cases pass | 0 |
| Vendor data matches published 2025 ranges | 30/30 after override, 1 allowlisted with reason | 0 |
| Trace coverage | 100% of reported numbers reachable from a trace step | 0 |
| Curated content citation coverage | 100% of rows, zero `PROVISIONAL` | 1 |
| Nutrients returning `UNKNOWN` for a complete profile | 0 of 30 | 1 |
| OCR field accuracy on real bottle photos | measured in Phase 4, threshold set from the measurement | 4 |

---

## 9. Constraints and dependencies

- **KDRI 2025 vendor CSVs** — 47 nutrient codes, 1052 band rows. Verified as genuine 2025 data (28/30 published ranges match exactly). One stale 2020 value found and corrected.
- **The source PDF is a press release, not the standards volume.** It validates our data but cannot populate it. Re-sourcing the full tables from kns.or.kr is a **pre-launch gate**.
- **KNHANES diet baselines are not yet sourced.** Blocks FR-11 completion; blocks Task 13.
- **`is_weight_scaled` is `false` on all 1052 rows.** Weight is collected and stored but affects no recommendation. This is a limitation of KDRI as published, not an implementation gap.
- **No `gender=ALL` row exists for adults.** Sex cannot be defaulted.
- **CLOVA OCR** for Korean label extraction, **Claude** for parsing, question phrasing, and chat.

---

## 10. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Diet baseline is one national constant | A vegan and a daily steak eater get the same iron baseline | Cited and documented; `UNKNOWN` where unsourced; questionnaire is the upgrade path |
| Curated content is hand-authored judgment | Elemental percentages, timing, interactions are ours, not KDRI's | Mandatory per-row citations; separate files from vendor data; git-PR review |
| Vendor CSVs are a near-perfect, not perfect, 2025 transcription | A stale value inside its published range passes undetected | Range fixture as a permanent test; full re-sourcing before launch |
| Form-scoped limits will keep appearing | A new form without a limit row falls through to the band default | `nutrient_limits` generalizes; resolution step 4 returns "no limit" rather than a wrong one |
| Korean regulatory posture unresolved | May constrain how recommendations are worded | Legal review before launch — see [PLAN.md §8](../PLAN.md#8-open-questions) |
| OCR misreads a curved label | Wrong dose enters the calculation | The confirm screen is a mandatory human checkpoint |

---

## 11. Release criteria

| Phase | Ships when |
|---|---|
| **0** | 14 tasks green: 1200-combination property test, 5 golden cases, range fixture, trace completeness |
| **1** | All 30 nutrients have cited baselines and forms; zero `PROVISIONAL`; interaction table cites named references |
| **2** | A user can complete the wizard by hand and receive a correct four-block report with expandable traces |
| **3** | Free-text supplement entry parses and reaches the engine only through the confirm screen |
| **4** | Photo entry converges on the same confirm screen; accuracy measured |
| **5** | Follow-up questions are engine-derived and capped at 3 |
| **6** | Why-chat answers from the trace and refuses new dosing |
| **7** | Magic-link auth, immutable report versions, history chains |
