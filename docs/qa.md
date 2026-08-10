# QA 테스트 케이스 — 영양제 추천 엔진

**Related:** [prd.md](prd.md) · [기능명세서.md](기능명세서.md) · [api.md](api.md) · [권한정책.md](권한정책.md)

Case IDs are stable and referenced from commit messages. `FR-xx` maps to [prd.md §5](prd.md#5-functional-requirements).

**Severity:** **S1** wrong or unsafe number reaches a user · **S2** feature broken, no safety impact · **S3** cosmetic.

The failure this suite exists to catch is not the crash. It is the **plausible wrong number** — no exception, no error, just a confident bad recommendation. Cases marked ⚠️ are exactly that class.

---

## DV — Data loading & validation (Phase 0)

| ID | Sev | Case | Expected |
|---|---|---|---|
| DV-01 | S1 | Load vendor CSVs | 47 nutrient codes, 1052 band rows |
| DV-02 | S1 | Parse blank `ul_limit` | `None`, not `0.0` ⚠️ a 0 upper limit would block every recommendation |
| DV-03 | S1 | In-scope derivation | Exactly 30: 14 vitamins + 15 minerals + `epa_dha` |
| DV-04 | S1 | `leucine`, `energy`, `water` in scope? | Excluded |
| DV-05 | S1 | Filter to adult scope | Exactly **300** rows |
| DV-06 | S1 | Rectangularity | 300 distinct `(code, sex, age_min, age_max)` keys — no duplicates |
| DV-07 | S1 | Sex values after filter | `{M, F}` only. No `ALL` |
| DV-08 | S1 | Rows under 19 after filter | Zero |
| DV-09 | S1 | Pregnancy rows `(0,99)` after filter | Zero ⚠️ these are deltas (`iron +9`), absolutes if read directly |
| DV-10 | S1 | Null `ri_base` after filter | Zero |
| DV-11 | S1 | Apply `overrides.csv` | magnesium M 15-18: 410 → **380** |
| DV-12 | S1 | Override with blank `source` | Raises `ValueError` mentioning `source` |
| DV-13 | S2 | Override matching no vendor row | Raises, names the orphan patch |
| DV-14 | S1 | Row count after overrides | Unchanged — patches replace, never append |
| DV-15 | S1 | 2025 range check, patched data | Zero deviations |
| DV-16 | S1 | 2025 range check, **unpatched** | Reports magnesium ⚠️ proves the check can still fail |
| DV-17 | S1 | Range check runs before scope filter | Confirmed — filtering first hides the 15-18 defect |
| DV-18 | S2 | RNI nutrient range selection | Infant bands `(0,5)`, `(6,11)` excluded |
| DV-19 | S2 | AI nutrient range selection | All bands included |
| DV-20 | S2 | `epa_dha` allowlist | Skipped, reason non-empty |
| DV-21 | S1 | Limit rows load | niacin has 2 form-scoped; magnesium 1 nutrient-wide |
| DV-22 | S1 | Limit with invalid `ul_basis` | Raises |
| DV-23 | S1 | Uncited curated row (any file) | Raises, names the file |
| DV-24 | S1 | Folate unit split | `target_unit = µg DFE`, `ul_unit = µg` |
| DV-25 | S1 | Form factor defaults | `target_factor = ul_factor = 1.0` where unspecified |
| DV-26 | S1 | Split-unit nutrient missing factors | Raises |
| DV-27 | S1 | Missing profile for in-scope nutrient (Phase 1) | Raises, lists missing codes |
| DV-28 | S1 | `PROVISIONAL` baseline survives to Phase 1 | Test fails |
| DV-29 | S2 | `elemental_pct` outside `(0, 1]` | Raises |
| DV-30 | S2 | Unknown `severity` in interactions | Raises |
| DV-31 | S1 | Seed asserts run at startup | Failure aborts startup, does not degrade |

---

## EN — Engine arithmetic (Phase 0)

### Band lookup

| ID | Sev | Case | Expected |
|---|---|---|---|
| EN-01 | S1 | iron, F, 34 | `ri_base = 12.0` |
| EN-02 | S1 | iron, M, 34 | `ri_base = 8.0` ⚠️ defaulting sex under-doses the population that most needs iron |
| EN-03 | S1 | Age 19 (lower boundary) | Matches `(19,29)` |
| EN-04 | S1 | Age 29 / 30 | `(19,29)` / `(30,49)` — no overlap, no gap |
| EN-05 | S1 | Age 49/50, 64/65, 74/75 | Correct band each side |
| EN-06 | S2 | Age 99, age 120 | Both match `(75,99)`; 120 does not raise |
| EN-07 | S1 | Age 18 | `BandNotFound` / refusal |
| EN-08 | S2 | Unknown nutrient code | `BandNotFound`, no silent zero |

### Limit resolution

| ID | Sev | Case | Expected |
|---|---|---|---|
| EN-10 | S1 | niacin + 니코틴아미드 | 850 mg NE, `supplemental_only` |
| EN-11 | S1 | niacin + 니코틴산 | 35 mg NE ⚠️ wrong row either blocks a safe dose or permits a 14× overdose |
| EN-12 | S1 | niacin, no form declared | Falls to band `ul_limit` 35 (conservative) |
| EN-13 | S1 | magnesium, no form | 350, `supplemental_only`, `applies_to_form = null` |
| EN-14 | S1 | zinc, no curated limit | Band 35, `total_intake` |
| EN-15 | S1 | biotin | `None` |
| EN-16 | S1 | calcium F 19-29 vs F 30-49 | 2500 vs 2000 ⚠️ UL varies **within** a nutrient; never cache per nutrient |
| EN-17 | S2 | Two forms of one nutrient declared | Most specific match wins, deterministically |

### Intake accounting

| ID | Sev | Case | Expected |
|---|---|---|---|
| EN-20 | S1 | 400 mg 비스글리시네이트 | 56.4 toward target and limit |
| EN-21 | S1 | 600 mg 산화마그네슘 | 361.8 |
| EN-22 | S1 | 200 mg 산화마그네슘 × 2/day | 241.2 |
| EN-23 | S1 | 200 µg 엽산 | **340** toward target, **200** toward limit ⚠️ collapsing them under-counts by ~70% |
| EN-24 | S2 | Unknown form string | Factors 1.0, dose treated as elemental |
| EN-25 | S2 | `form_ko = null` | Same as EN-24 |
| EN-26 | S2 | Empty supplement list | Both totals 0.0 |
| EN-27 | S2 | `doses_per_day = 0.5` | Halves both totals |

### Computation

| ID | Sev | Case | Expected |
|---|---|---|---|
| EN-30 | S1 | `round_down(57.6)` | `57.0` |
| EN-31 | S1 | `round_down(293.6)` | `290.0` |
| EN-32 | S1 | `round_down` never rounds up | Verified across a random sweep |
| EN-33 | S1 | `round_down(0)`, `round_down(-5)` | `0.0` both |
| EN-34 | S1 | `supplemental_only` excludes diet | magnesium M 34, no supplements → `headroom = 350.0` ⚠️ subtracting diet gives −157 and calls a healthy adult over-supplemented |
| EN-35 | S1 | `total_intake` includes diet | iron F 34 → `headroom = 45 − 7.2` |
| EN-36 | S1 | No limit | `recommend == round_down(gap)`, never unbounded |
| EN-37 | S1 | `recommend` never negative | Holds when `headroom < 0` |
| EN-38 | S1 | Missing diet baseline | `UNKNOWN`, `recommend = 0`, reason stated |
| EN-39 | S1 | `gap` floors at 0 | Never negative |

### Status & ordering

| ID | Sev | Case | Expected |
|---|---|---|---|
| EN-40 | S1 | `headroom < 0` | `OVER` |
| EN-41 | S1 | `gap > 0`, headroom ok | `DEFICIT` |
| EN-42 | S1 | `gap == 0` | `ADEQUATE` |
| EN-43 | S1 | No band or no baseline | `UNKNOWN` |
| EN-44 | S1 | `OVER` present | Sorts first |
| EN-45 | S2 | `UNKNOWN` entries | Sort last |
| EN-46 | S2 | Two deficits | Larger gap-to-target ratio first |
| EN-47 | S1 | Report length | Exactly 30 results |

### Golden cases ⚠️ — hand-computed, from [spec §6.7](superpowers/specs/2026-08-10-supplement-recommendation-design.md)

| ID | Sev | Case | Expected | Naive engine says |
|---|---|---|---|---|
| EN-50 | S1 | Mg 비스글리시네이트 400 mg, M 34, baseline 0.70 | target 380, diet 266, supp **56.4**, gap 57.6, headroom 293.6, **recommend 57**, `DEFICIT` | gap 0 — "you're fine", user is 58 mg short |
| EN-51 | S1 | 산화마그네슘 600 mg, M 34 | supp **361.8**, headroom **−11.8**, `OVER`, recommend 0 | within limit |
| EN-52 | S1 | Sex requirement | iron F 12 ≠ M 8; no adult `ALL` band exists | defaults, under-doses women |
| EN-53 | S1 | 니코틴아미드 500 mg, M 34 | headroom **350**, `ADEQUATE` | `35 − 500 = −465` → false `OVER` |
| EN-54 | S1 | 니코틴산 500 mg, M 34 | `OVER` | 850 row → permits 14× overdose |
| EN-55 | S1 | 엽산 200 µg, F 34, baseline 0.40 | diet 160, target-side **340**, gap **0**, headroom 800, `ADEQUATE` | gap 40 → recommends more to someone at target |

### Exhaustive property

| ID | Sev | Case | Expected |
|---|---|---|---|
| EN-60 | S1 | All 300 bands × 4 intake levels | 1200 combinations, all invariants hold |
| EN-61 | S1 | `recommend ≥ 0` | Always |
| EN-62 | S1 | `recommend ≤ gap` | Always |
| EN-63 | S1 | `recommend ≤ max(0, headroom)` when limit exists | Always |
| EN-64 | S1 | `recommend == round_down(gap)` when no limit | All 12 no-UL nutrients |

### Trace

| ID | Sev | Case | Expected |
|---|---|---|---|
| EN-70 | S1 | Every result has a trace | No empty trace |
| EN-71 | S1 | `recommend > 0` | Trace contains `target.from_band`, `diet.baseline`, `recommend.computed` |
| EN-72 | S1 | Limit applied | `recommend.computed` carries the limit's `source` |
| EN-73 | S1 | Every reported number is traceable | Walk the report, assert coverage |
| EN-74 | S1 | Engine imports | No import path from `engine.py` to `llm/` ([TB-1](권한정책.md#tb-1--engine--llm-module-boundary)) |
| EN-75 | S2 | `energy_ratio` in `engine.py` | Absent |

---

## SC — Scope gates & refusals

| ID | Sev | Case | Expected |
|---|---|---|---|
| SC-01 | S1 | age 18 | `AGE_OUT_OF_SCOPE`, referral, **no numbers** |
| SC-02 | S1 | age 19 | Proceeds |
| SC-03 | S1 | `is_pregnant: true` | `PREGNANCY_OUT_OF_SCOPE`, 산부인과 referral, no numbers |
| SC-04 | S1 | `is_lactating: true` | Same ⚠️ lactation deltas absent from source data |
| SC-05 | S1 | `sex` omitted | `SEX_REQUIRED` — never defaults |
| SC-06 | S2 | `sex: "X"` | 422 |
| SC-07 | S2 | Unknown drug class | Report succeeds; affected nutrients show 평가되지 않음 |
| SC-08 | S1 | Every refusal | Carries `code`, Korean `message`, and a reason |
| SC-09 | S1 | Refusal returns a zero-filled report? | No — refusals never return `results` |

---

## IN / CF — Intake, parsing, confirm screen

| ID | Sev | Case | Expected |
|---|---|---|---|
| IN-01 | S2 | "산화마그네슘 400mg 아침에 1알" | Parses to magnesium / 산화마그네슘 / 400 / mg / 1 |
| IN-02 | S2 | Synonym "Mg 400mg" | Matches via `synonyms_ko_label` |
| IN-03 | S2 | Unmapped product name | Returned as `unresolved`, **not dropped** |
| IN-04 | S1 | Parser output submitted directly to `POST /api/reports` | No such path exists ([TB-2](권한정책.md#tb-2--confirm-screen-human-checkpoint)) |
| IN-05 | S2 | OCR on a blurred label | Low-confidence fields flagged for confirmation |
| IN-06 | S1 | Photo retained after OCR? | Discarded; only parsed rows persist |
| CF-01 | S1 | Both paths render | One confirm screen for OCR and manual alike |
| CF-02 | S1 | Every row editable | nutrient, form, dose, unit, doses/day |
| CF-03 | S1 | Unresolved item present | Marked 확인 필요; submit blocked → `UNRESOLVED_INTAKE` |
| CF-04 | S1 | "마그네슘 400mg" ambiguous | Prompts elemental vs compound ⚠️ ~2.5× difference |
| CF-05 | S2 | User edits a parsed dose | Edited value used, not the parsed one |
| CF-06 | S2 | User deletes a row | Excluded from computation |

---

## RP — Report rendering

| ID | Sev | Case | Expected |
|---|---|---|---|
| RP-01 | S2 | Four blocks present | 입력 요약 · 현재 상태 분석 · 추천 · 참고 |
| RP-02 | S1 | `OVER` nutrient | Reduction instruction, top of report, not a dose |
| RP-03 | S1 | `UNKNOWN` nutrient | Target and current shown; **no recommendation**; reason stated |
| RP-04 | S1 | Weight entered | Report states it affects no recommendation ⚠️ implying precision we don't have is the failure |
| RP-05 | S2 | Block ④ AMDR | Labelled reference, explicitly not an assessment |
| RP-06 | S1 | Block ④ trace | None — nothing was computed. Asymmetry is intentional and visible |
| RP-07 | S2 | Trace expansion | Every number in blocks ② and ③ expands |
| RP-08 | S1 | Disclaimer | Present on every report |
| RP-09 | S2 | Interaction flag | Rendered with severity and spacing instruction |
| RP-10 | S2 | Suggested form | Includes *why that form*, not just the name |

---

## VR — Versioning

| ID | Sev | Case | Expected |
|---|---|---|---|
| VR-01 | S1 | 입력 수정 | New row v2, `parent_id = v1`. v1 unchanged |
| VR-02 | S1 | Update endpoint exists? | No — immutability is structural |
| VR-03 | S1 | `GET` after `POST` | Byte-identical `results` |
| VR-04 | S2 | v1 prefill | Wizard populated from `profile_json` |
| VR-05 | S2 | History | Chains rendered, newest first |
| VR-06 | S2 | Delete an ancestor | Descendant `parent_id` → null; chain survives |
| VR-07 | S1 | Report reproducible alone | Recompute from `profile_json` matches `result_json` |

---

## CH — Why-chat

| ID | Sev | Case | Expected |
|---|---|---|---|
| CH-01 | S2 | "왜 이렇게 나왔나요?" | Answer derived from trace only |
| CH-02 | S1 | "그럼 600mg 먹어도 되나요?" | Refuses to issue a new dose |
| CH-03 | S1 | Chat writes to `reports`? | Never ([TB-5](권한정책.md#tb-5--chat-read-only)) |
| CH-04 | S1 | Question about an untraced value | States it cannot answer rather than improvising |
| CH-05 | S2 | User reveals a missing supplement | Points to 입력 수정 |
| CH-06 | S1 | Chat bound to version | v1 chat unaffected by v2 |
| CH-07 | S1 | Chat on another user's report | 404 |

---

## AU / SE — Auth, privacy, security

| ID | Sev | Case | Expected |
|---|---|---|---|
| AU-01 | S2 | Magic link request | Identical response whether or not the email exists |
| AU-02 | S1 | Token reuse | Rejected; `used_at` set on first use |
| AU-03 | S1 | Expired token (>15 min) | Rejected |
| AU-04 | S1 | Sign-in with session reports | Claimed to the `user_id` in one transaction |
| AU-05 | S1 | Double-claim | Second attempt fails ⚠️ the one place ownership changes hands |
| AU-06 | S1 | Claim a report already owned | Rejected |
| AU-07 | S2 | Rate limit on link requests | 5/hour/email, 6th returns 429 with `Retry-After` |
| SE-01 | S1 | `GET` another user's report | **404**, not 403 — a 403 confirms existence |
| SE-02 | S1 | Direct `SELECT FROM reports` outside the accessor | Codebase scan finds none ([TB-3](권한정책.md#tb-3--user_id-accessor-data-isolation)) |
| SE-03 | S1 | Report contents in application logs | Never |
| SE-04 | S1 | Health data in error responses | Never; `INTERNAL` carries no contents |
| SE-05 | S1 | Delete user | Cascades to reports and chat messages |
| SE-06 | S2 | Session cookie flags | HTTP-only, `Secure`, `SameSite=Lax` |
| SE-07 | S1 | SQLite foreign keys | `PRAGMA foreign_keys = ON` per connection ⚠️ off by default, constraints silently ignored |
| SE-08 | S2 | 주민등록번호 or name stored | Never |

---

## PF — Performance & operations

| ID | Sev | Case | Expected |
|---|---|---|---|
| PF-01 | S2 | Full 30-nutrient report | < 200 ms server-side, excluding LLM |
| PF-02 | S2 | Sensitivity analysis | ~360 engine passes within the same budget |
| PF-03 | S2 | `GET /api/health` | `band_rows: 300` ⚠️ any other number means the seed filter drifted |
| PF-04 | S1 | Seed assertion failure | Startup aborts; the app does not serve degraded data |
| PF-05 | S2 | Reseed idempotency | Repeated seeding yields identical tables |

---

## Coverage map

| Area | Cases | Automated at |
|---|---|---|
| DV | 31 | Phase 0-1, `test_loader` · `test_ranges` · `test_curated` |
| EN | 46 | Phase 0, `test_engine` · `test_lookup` · `test_golden` · `test_property` |
| SC | 9 | Phase 0 engine, Phase 2 API |
| IN / CF | 12 | Phase 3-4 |
| RP | 10 | Phase 2 |
| VR | 7 | Phase 7 |
| CH | 7 | Phase 6 |
| AU / SE | 15 | Phase 7 (SE-02, SE-07 earlier) |
| PF | 5 | Phase 2+ |
| **Total** | **142** | |

**77 cases (DV + EN) are automated in Phase 0-1**, before any UI exists. That is deliberate: every one of them guards a number, and a wrong number is the only defect in this product that causes harm rather than annoyance.
