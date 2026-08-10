# AI Supplement Recommendation Service — MVP Design Spec

**Date:** 2026-08-10
**Status:** Approved for planning
**Scope:** MVP

---

## 1. Problem

Consumers face an information barrier they cannot cross alone. Magnesium is the canonical case: a dozen chemical forms, each with different elemental content, absorption profile, GI tolerance, and optimal timing. A person who wants "better sleep" has to learn which form serves that goal, how much elemental magnesium it delivers, how it stacks with what they already take, whether it collides with their medication, and when to take it.

The service collapses that research into an answer. User supplies basic accurate facts; system computes an evidence-based recommendation.

### Core user question

> "What should I take, how much, and when?"

### Value proposition

Lowering the barrier to analytical data. The differentiator is not conversation — it is that **the numbers are correct and traceable to a national guideline**.

---

## 2. Scope

### In scope

- 30 nutrients: 14 vitamins + 15 minerals + EPA/DHA
- Adults 19+ only
- Deterministic dose engine over KDRI 2025
- Supplement form selection, elemental conversion, timing guidance
- Current-supplement subtraction via photo OCR or manual entry
- Drug interaction flags from a curated table
- Health checkup biomarkers as prioritization context
- Report history with versioning
- Grounded "why did you recommend this" chat

### Out of scope for MVP

| Excluded | Reason |
|---|---|
| Under-19 | Pediatric dosing liability; age-band collision in source data |
| Pregnancy / lactation | Highest-liability population; lactation deltas absent from data |
| Therapeutic dosing above RI | Clinical treatment, not nutrition guidance |
| Macronutrients, amino acids, energy, water | Not sold as supplements against a KDRI band. AMDR is seeded and displayed as reference (§5.4), never computed. |
| Sodium recommendation | Reduction target (CDRR), not a supplement; status display only |
| Product catalog / brand-level pricing | No dataset available |
| MCP server | `mcp/` stays empty this round |

---

## 3. Locked design decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Form/timing/interaction knowledge source | Curated files + LLM fallback tagged low-confidence | Not present in either CSV; determinism required where it affects dosing |
| 2 | App shape | Wizard → report → chat | Guarantees complete inputs; report is a stable artifact to anchor chat and history |
| 3 | Stack | FastAPI + Next.js + SQLite | Matches existing dir layout; Python suits the numeric work |
| 4 | Language | Korean only | Source of truth is Korean national guideline |
| 5 | Age handling | Adults 19+ only | Eliminates the months/years band collision entirely |
| 6 | Pregnancy | Excluded, routed to clinician | Data supports only pregnancy, not lactation; half coverage is worse than none |
| 7 | Target rule | `target = ri_base`, UL as hard cap | Matches "target − current = what to take" |
| 8 | Data gap fixes | `overrides.csv` layered on vendor CSVs | Keeps the national-guideline / our-judgment line greppable |
| 9 | Current intake entry | OCR **or** manual, both to one confirm screen | Photo for speed, manual for control, single validation path |
| 10 | Biomarkers | Priority and context only, never move the number | Consistent with decision 7; stays on the nutrition side of the medical line |
| 11 | Diet accounting | Per-nutrient national baseline constant | Prevents systematic over-recommendation |
| 12 | Auth | Email magic link | Cross-device history without password handling |
| 13 | Nutrient scope | Vitamins + minerals + EPA/DHA | The set that exists as products on a shelf |
| 14 | Medications | Curated deterministic table only | Highest-harm hallucination surface; LLM never authors an interaction |
| 15 | Why-chat | Trace-grounded, read-only + Edit Inputs button | Chat cannot mint doses; edits go through the engine |
| 16 | Follow-up questions | Engine sensitivity analysis, LLM phrases only | Cannot ask for data that wouldn't change an answer |
| 17 | AMDR / macronutrients | Ingest as reference, display only | An AMDR is a ratio of actual energy intake; without diet logging there is no denominator |
| 18 | Form-dependent upper limits | Generalized `nutrient_limits` resolution | Magnesium, niacin, and folate are the same bug; three ad-hoc fixes would be three future bugs |
| 19 | Folate DFE conversion | Fixed 1.7×, dual accounting | One constant, one citation, one test; covers the with-meal common case |
| 20 | 2025 data provenance | CSVs as source of truth, PDF as automated test fixture | The press release validates but cannot populate; the range test is what caught magnesium 410 |

---

## 4. Architecture

```
backend/                 FastAPI + SQLAlchemy + SQLite
  data/
    vendor/              read-only, never edited
      nutrient_codes.csv
      kdri_standards.csv
      2025_KDRI_보도자료.pdf          source document for §5.1.1
    curated/             authored by us, every row cited
      overrides.csv                  value corrections
      nutrient_limits.csv            form-scoped upper limits
      energy_ratios.csv              AMDR, reference only
      nutrient_profiles.yaml
      interactions.csv
  engine/                pure functions — no LLM, no I/O, no DB
  llm/                   every LLM call site, isolated behind an interface
  api/                   FastAPI routes
  db/                    models, seed
frontend/                Next.js App Router, Korean, Tailwind
docs/superpowers/specs/  this file
```

### The one architectural rule

> **The LLM never produces a number.**

The engine computes. The LLM parses input into structured data and phrases output into Korean. Every dose, target, cap, and interaction flag originates in a pure function reading a cited table. This boundary is enforced by module structure: `engine/` has no import path to `llm/`.

---

## 5. Data layer

### 5.1 Vendor data — verified facts

`nutrient_codes.csv` — 47 rows.
Columns: `nutrient_code, nutrient_ko, group_name, kdri_unit, synonyms_ko_label, has_ear, has_rni, has_ai, has_ul, has_cdrr, kdri_version`.
`synonyms_ko_label` is pipe-delimited and directly powers parser matching, e.g. magnesium → `Mg|산화마그네슘|구연산마그네슘`.

`kdri_standards.csv` — 1052 rows.
Columns: `id, nutrient_code, age_min, age_max, gender, ri_base, ul_limit, is_weight_scaled`.

Facts established by inspection, each of which drives a design rule:

| Fact | Consequence |
|---|---|
| `(0,5)` and `(6,11)` are **months**; `(3,5)`, `(6,8)`, `(9,11)` are **years** | Collision at age 5 and 6. Resolved by excluding sub-19 entirely. |
| `gender=F, age 0-99` rows are **pregnancy deltas**, not absolutes (iron `+9`, folate `+220`, magnesium `+40`) | Must be filtered at seed time or they corrupt every female lookup |
| `is_weight_scaled` is `false` on all 1052 rows | Weight cannot affect any in-scope nutrient. See §5.7. |
| Magnesium has `has_ul=true` but **zero UL values** in any row | Requires an override row |
| Adult in-scope rows: **exactly 300** = 30 × 5 bands × 2 sexes | Rectangular; enables exhaustive testing |
| **No `gender=ALL` rows exist for adults** | Sex is required input. No fallback path exists. |
| Zero blank `ri_base` in adult scope | No missing-target handling needed for adults |
| 12 of 30 nutrients have no adult UL | Only magnesium is flagged `has_ul=true`; the other 11 genuinely have no established KDRI upper limit |
| Calcium UL varies **within** a nutrient by band (F 19-29 = 2500, F 30+ = 2000) | UL must be read from the band row, never cached per nutrient |

Nutrients with no adult UL, correctly: biotin, chloride, chromium, EPA/DHA, pantothenic acid, potassium, riboflavin, sodium, thiamin, vitamin B12, vitamin K. Plus magnesium, incorrectly — supplied by `nutrient_limits` (§5.3).

`nutrient_codes.csv` carries a single `kdri_unit` per nutrient. Seeding splits it into `target_unit` and `ul_unit`, which are identical for 29 of 30 nutrients and differ for folate (§5.5).

### 5.1.1 Edition verification

`data/vendor/[12.31.수+석간]+영양소+적정+섭취기준+개정 (1).pdf` — the Ministry of Health and Welfare press release announcing the 2025 revision, 14 pages. Attachment 3 (붙임3) publishes the 2020→2025 RNI/AI range for every nutrient.

Testing our CSVs against both editions on the 12 nutrients whose ranges differ:

| Edition | Nutrients matching |
|---|---|
| 2020 | **0 / 12** |
| 2025 | **11 / 12** |

Corroborating: choline is present in our data and was 제정 (newly created) in 2025, absent from 2020. Nutrient count reconciles exactly — 47 codes − 9 individually-split amino acids + 총당류 + 콜레스테롤 = **41**, the PDF's stated total.

**Conclusion: `kdri_version = 2025` is accurate.** The B6 upper limit of 50 mg/일, the choline AI and UL, and the folate `µg DFE` unit are all already present. Three revisions that looked like work turned out to be already done, and the fourth turned out to be a schema problem rather than a value edit.

The single discriminator that failed:

| Nutrient | Our value | 2025 published max | Verdict |
|---|---|---|---|
| Magnesium, M 15-18 | 410 | 380 | **stale 2020 value** |

Age 15-18 is outside MVP scope, so it changes no adult recommendation. It matters as evidence: the CSV is a near-perfect 2025 transcription, not a perfect one. Bands the press release does not enumerate may hold similar defects, which is why §13 promotes the range comparison to a permanent test rather than a one-time check.

The press release **validates but cannot populate** — it publishes ranges and narrative, not the age×sex tables. Full re-sourcing from mohw.go.kr or kns.or.kr is a pre-launch gate (§15).

### 5.2 `overrides.csv` — value corrections

Layered on vendor data at seed time. Vendor files are never edited, so a fresh KDRI release can be dropped in and re-imported.

```csv
nutrient_code,gender,age_min,age_max,field,value,source,note
magnesium,M,15,18,ri_base,380,"KDRI 2025 붙임3 마그네슘 70~380","2020 잔존값 410 수정 — MVP 범위 밖"
```

Every row is a deliberate deviation from the vendor file and must carry a source. Upper limits are **not** expressed here — they moved to §5.3.

### 5.3 `nutrient_limits.csv` — form-scoped upper limits

An upper limit is not a scalar per `(nutrient, age, sex)`. It is a function of the **chemical form** in the pill. Three of our 30 nutrients already prove it:

| Nutrient | The limit depends on | Values |
|---|---|---|
| Magnesium | supplemental vs food | 350 mg supplemental; none for total intake |
| Niacin | nicotinic acid vs nicotinamide | 35 mg NE vs **850 mg NE** |
| Folate | synthetic folic acid vs food folate | 1000 **µg**, not µg DFE |

Encoding these as three special cases would produce three future bugs. One table resolves all of them:

```csv
nutrient_code,applies_to_form,age_min,age_max,sex,ul_value,ul_unit,ul_basis,source
magnesium,,19,99,ALL,350,mg,supplemental_only,"KDRI 2025 마그네슘 상한섭취량"
niacin,니코틴산,19,99,ALL,35,mg NE,supplemental_only,"KDRI 2025 — 2020 수준 유지"
niacin,니코틴아미드,19,99,ALL,850,mg NE,supplemental_only,"KDRI 2025 보도자료 p.10 — 1,000→850 하향"
folate,,19,99,ALL,1000,µg,supplemental_only,"KDRI 2025 보도자료 p.10 — UL은 µg/일 유지"
```

`applies_to_form` empty means *all supplemental forms of this nutrient*. Magnesium and folate need that: their limits govern supplement-sourced intake generally, not one compound. Niacin needs the form-specific rows.

Resolution order, most specific wins:

1. `nutrient_limits` row matching nutrient + the user's declared form
2. `nutrient_limits` row for the nutrient with `applies_to_form` empty
3. `kdri_bands.ul_limit` from vendor data, basis `total_intake`
4. No limit — see §6.2

> **Deviation from the literal decision.** Decision 18 said "move UL onto `nutrient_forms`". This puts it in its own table with a nullable form reference instead, because magnesium's and folate's limits are not per-form and would need fabricated rows against every form to fit there. Same mechanism and same resolution path, normalized. Flagging it rather than silently reinterpreting.

### 5.4 `energy_ratios.csv` — AMDR, reference only

```csv
macronutrient,age_min,age_max,pct_min,pct_max,kdri_version,source,changed_2025
carbohydrate,1,99,50,65,2025,"KDRI 2025 보도자료 p.7",하한선 하향 (55→50)
protein,1,99,10,20,2025,"KDRI 2025 보도자료 p.7",하한선 상향 (7→10)
fat,1,99,15,30,2025,"KDRI 2025 보도자료 p.7",유지
```

Seeded and displayed as educational context. **The engine never reads this table.**

An AMDR is a percentage of actual energy intake. Computing one requires knowing what the user ate, and diet logging is out of scope (§2) — there is no denominator. Presenting a computed macro ratio without it would be fabrication. The report shows the official ranges as reference and says so.

### 5.5 `nutrient_profiles.yaml`

Per nutrient. Deep for the top 10 (magnesium, iron, vitamin D, zinc, calcium, EPA/DHA, B12, folate, vitamin C, B6), thin for the remaining 20.

```yaml
magnesium:
  diet_baseline_pct: 0.70          # sourced from KNHANES in Phase 1
  diet_baseline_source: "KNHANES <year> <table>"
  forms:
    - name_ko: 산화마그네슘
      elemental_pct: 0.603
      absorption: low
      gi_note: 완하 작용 강함
      source: "..."
    - name_ko: 구연산마그네슘
      elemental_pct: 0.161
      absorption: high
      gi_note: 보통
      source: "..."
    - name_ko: 마그네슘 비스글리시네이트
      elemental_pct: 0.141
      absorption: high
      gi_note: 낮음, 위장 민감자 적합
      source: "..."
  timing:
    when: evening
    with_food: true
    split_dose_above_mg: 400
    rationale_ko: "..."
    source: "..."
```

`elemental_pct` values above are illustrative. Phase 1 sources every one; no value ships without a citation.

Forms may also carry `target_factor`, which converts a labelled dose into target units when the two differ:

```yaml
folate:
  target_unit: µg DFE
  ul_unit: µg                        # §5.3 — UL governs synthetic folic acid
  forms:
    - name_ko: 엽산 (합성 folic acid)
      target_factor: 1.7             # 1 µg folic acid = 1.7 µg DFE, taken with food
      ul_factor: 1.0                 # UL counts raw µg
      source: "KDRI 2025 보도자료 p.10"
    - name_ko: 메틸엽산 (5-MTHF)
      target_factor: 1.7
      ul_factor: 1.0
      source: "..."
```

**One pill produces two numbers.** A 400 µg folic acid tablet contributes **680 µg DFE** toward the target and **400 µg** toward the upper limit. Treating them as one number under-counts folate intake by roughly 70% — enough to tell a woman already at target to take more. `target_factor` defaults to 1.0 for every other nutrient, so this costs nothing where it doesn't apply.

The 2.0× empty-stomach factor is deliberately not modelled. Fixed 1.7 covers the with-meal common case (decision 19); the constant is one line to revisit if it proves material.

### 5.6 `interactions.csv`

```csv
nutrient_code,drug_class,drug_examples_ko,effect,action,severity,source
calcium,levothyroxine,"레보티록신(씬지로이드)",흡수저해,4시간 이상 간격,high,"..."
magnesium,quinolone,"시프로플록사신, 레보플록사신",킬레이트 형성,2시간 이상 간격,high,"..."
vitamin_k,warfarin,"와파린",항응고 길항,담당의 상담 필수,critical,"..."
```

Fires as a hard rule. A drug class absent from the table returns `평가되지 않음 — 약사와 상담하세요`. The LLM is never asked to evaluate an interaction.

### 5.7 Weight

`is_weight_scaled` is `false` on every row, so weight scales nothing in the 30-nutrient scope. Weight remains an **optional** intake field and is stored on the profile, but the report states plainly that it does not affect any current recommendation. It becomes load-bearing only if protein and energy are added later (§14).

This is a limitation of KDRI as published, not an implementation shortcut.

### 5.8 Seeding

Idempotent script: load vendor CSVs → **verify against the 2025 range fixture (§13)** → filter to adults 19+ and the 30 in-scope codes → drop pregnancy delta rows → apply `overrides.csv` → load `nutrient_limits.csv`, `energy_ratios.csv`, and the curated YAML → write to SQLite.

The range check runs **before** filtering, on the full 1052 rows. Restricting to adults first would have hidden the magnesium 15-18 defect — the check is only worth having if it sees what MVP ignores.

Seed asserts on completion:
- exactly 300 KDRI band rows survive
- every surviving row has non-null `ri_base` and a `gender` of `M` or `F`
- zero rows with `age_min < 19`
- zero rows with `age_max = 99 AND age_min = 0`
- every in-scope nutrient has a `diet_baseline_pct` or is explicitly marked `baseline_source: none`
- every `nutrient_limits` row has a non-null `ul_basis`, `ul_unit`, and `source`
- every nutrient whose `target_unit` differs from its `ul_unit` has a `target_factor` on every form
- every curated row (`nutrient_profiles.yaml`, `interactions.csv`, `overrides.csv`, `nutrient_limits.csv`) has a non-empty `source`
- every RNI/AI range matches the 2025 published range, or is listed as a known exception with a reason

Failing any assert aborts startup. Bad data must never reach the engine.

---

## 6. Engine

Pure. No LLM, no network, no DB access — takes loaded tables as arguments. Fully testable in isolation.

### 6.1 Types

```python
Profile:
    age: int                          # required, >= 19
    sex: Literal["M", "F"]            # required — no ALL band exists
    weight_kg: float | None           # stored, unused (§5.7)
    supplements: list[SupplementIntake]
    medications: list[str]            # drug class codes
    biomarkers: list[Biomarker]
    goals: list[str]

SupplementIntake:
    nutrient_code: str
    form_ko: str | None               # None → assume label states elemental
    dose: float
    unit: str
    doses_per_day: float

NutrientResult:
    nutrient_code: str
    status: DEFICIT | ADEQUATE | OVER | UNKNOWN
    target: float
    from_diet: float
    from_supplements: float
    gap: float
    headroom: float | None
    recommend: float
    suggested_form: str | None
    timing: str | None
    interaction_flags: list[InteractionFlag]
    priority_score: float
    trace: list[TraceStep]
```

### 6.2 Algorithm, per nutrient

```
band     = lookup(sex, age)                    # exact match, asserted non-null
target   = band.ri_base                        # after overrides, in target_unit
diet     = target × nutrient.diet_baseline_pct

# dual accounting — one pill, two numbers (§5.5)
toward_target = Σ(dose × elemental_pct(form) × target_factor(form) × doses_per_day)
toward_limit  = Σ(dose × elemental_pct(form) × ul_factor(form)     × doses_per_day)

gap      = max(0, target − diet − toward_target)
limit    = resolve_limit(nutrient, declared_forms, age, sex)    # §5.3, 4-step order

if limit is None:                              # 12 of 30 nutrients — §5.1
    headroom = None
elif limit.basis == "supplemental_only":
    headroom = limit.value − toward_limit      # diet excluded — see §6.3
else:
    headroom = limit.value − diet − toward_limit

recommend = gap if headroom is None else min(gap, headroom)
recommend = round_down(recommend, 2 sig figs)
```

`round_down` never rounds toward the UL.

**No UL is not unlimited.** For the 12 nutrients without an established KDRI upper limit, `recommend` is capped by `gap` alone — the engine never recommends beyond the target, so absence of a ceiling can never produce an unbounded dose. The report labels these `상한섭취량 미설정` rather than implying safety at any dose.

### 6.3 Why the limit must be resolved through the form

Three of the 30 nutrients break a naive `ul_limit` lookup, each in a different way. All three are handled by the same resolution (§5.3).

**Magnesium — the target legitimately exceeds the limit.** Male 30-49: RI 380 mg, supplemental UL 350 mg. RI counts food; the UL does not. An engine computing `headroom = 350 − diet − current` with `diet = 266` gets `−157` before the user has swallowed anything, and reports a healthy adult as dangerously over-supplemented.

**Niacin — two limits, and the pill decides which.** 니코틴산 caps at 35 mg NE; 니코틴아미드 at 850 mg NE. A 500 mg nicotinamide supplement is within its limit and 14× over the other. Picking the wrong row either blocks a safe dose or permits a harmful one — the failure runs in both directions.

**Folate — the limit is in a different unit than the target.** Target in µg DFE, UL in µg. Comparing a DFE-denominated intake against a µg-denominated ceiling overstates intake by 1.7× and produces a false `OVER`.

The common shape: **an upper limit is a property of what is in the pill, not only of the person taking it.** Each gets a dedicated golden test (§13).

### 6.4 Status

| Status | Condition |
|---|---|
| `DEFICIT` | `gap > 0` |
| `ADEQUATE` | `gap == 0` and not over |
| `OVER` | `current` (or `diet + current`, per basis) `> ul` |
| `UNKNOWN` | no band row, or `diet_baseline_source: none` |

**`OVER` is a first-class output.** When intake already exceeds the upper limit the report leads with a reduction instruction. Over-supplementation is the more common real-world failure than deficiency, and no competing product surfaces it.

`UNKNOWN` shows target and current but **no recommendation number**. When the diet baseline is unsourced, subtracting nothing from the target would systematically over-recommend — so the system declines to answer rather than guess.

### 6.5 Priority ordering

1. `OVER` — safety first
2. Biomarker-flagged nutrients (low hemoglobin → iron)
3. `DEFICIT` by gap-to-target ratio, descending
4. Goal-matched nutrients
5. `ADEQUATE`
6. `UNKNOWN`

### 6.6 Trace

Every step appends `TraceStep{rule_id, inputs, output, citation}`. The trace is persisted with the report and is the sole context given to the why-chat (§8).

### 6.7 Worked examples

**A. Magnesium bisglycinate 400 mg, male 34** — elemental conversion flips the answer

```
band M 30-49          target   = 380 mg
diet 380 × 0.70       diet     = 266 mg
400 mg × 0.141        current  =  56.4 mg elemental
gap                            =  57.6 mg   → DEFICIT
headroom 350 − 56.4            = 293.6 mg   (supplemental_only)
recommend min(57.6, 293.6)     =  57 mg
```

An engine reading the label's `400` as elemental computes `gap = 0` and tells the user they are fine. They are 58 mg short. This is the single most valuable calculation in the product.

**B. Magnesium oxide 600 mg, male 34** — `OVER`

```
600 mg × 0.603        current  = 361.8 mg elemental
supplemental UL 350            → OVER by 11.8 mg
recommend                      = reduce
```

600 mg MgO tablets are sold on the Korean market. A user taking one daily is over the supplemental upper limit and has no way to know.

**C. Iron, female 34 vs male 34** — why sex is required, not defaulted

`F 19-49 RI = 12 mg`, `M = 8 mg`. No `ALL` band exists. Defaulting to the lower value under-doses exactly the population that most needs iron.

**D. Nicotinamide 500 mg, male 34** — the wrong limit row invents a warning

```
band M 30-49          target       =  14 mg NE
resolve_limit(니코틴아미드)         = 850 mg NE, supplemental_only
toward_limit                       = 500 mg NE
headroom 850 − 500                 = 350 mg NE   → ADEQUATE
```

An engine reading the band's `ul_limit = 35` (the nicotinic acid figure) computes `35 − 500 = −465` and tells the user to stop a supplement that is within its actual limit. The same lookup error inverted — a 500 mg nicotinic acid product read against the 850 row — would wave through a dose 14× over its ceiling.

**E. Folic acid 200 µg, female 34** — the DFE conversion flips the answer

```
band F 30-49          target       = 400 µg DFE
diet 400 × 0.40                    = 160 µg DFE      (illustrative baseline)
200 µg × 1.7          toward_target= 340 µg DFE
gap max(0, 400−160−340)            =   0             → ADEQUATE
toward_limit                       = 200 µg          (raw, not DFE)
headroom 1000 − 200                = 800 µg
```

An engine treating the label's `200` as DFE computes `gap = 40` and recommends more folate to someone already at target. The unit split is not bookkeeping — it changes the recommendation.

---

## 7. Follow-up questions

The engine runs sensitivity analysis rather than letting the LLM decide what to ask.

1. Run the engine on the partial profile.
2. For each missing field, re-run twice with the field pinned to its plausible minimum and maximum.
3. Record the maximum swing in any nutrient's `recommend` value.
4. Rank fields by swing. Fields exceeding a threshold become questions.
5. Send the top 3 to the LLM, which phrases them in natural Korean.

Roughly 360 pure-arithmetic runs, sub-millisecond total.

The structural consequence: **the system cannot ask for information that would not change its answer.** Question relevance is a property of the arithmetic, not of a prompt.

---

## 8. LLM boundary — four call sites

| # | Site | Input | Output | Constraint |
|---|---|---|---|---|
| 1 | OCR | bottle photo | raw text | vision only, no interpretation |
| 2 | Parse | text (from OCR or manual) | structured intake list | validated against `synonyms_ko_label`; **user confirms before any math** |
| 3 | Phrase follow-ups | engine's ranked gap list | Korean questions | cannot invent a question off-list |
| 4 | Why-chat | trace JSON + user question | Korean explanation | read-only; refuses to produce new dosing |

Anything failing validation at site 2 surfaces on the confirm screen as unresolved, never silently dropped.

The confirm screen is the trust boundary. Both OCR and manual entry converge on it, so there is exactly one path from unstructured input to the engine, and a human approves it.

---

## 9. Report

Three blocks, matching the requested output shape.

**1. 입력 요약** — profile as parsed, with an `입력 수정` button.

**2. 현재 상태 분석** — per nutrient: target, from diet, from supplements, gap, status. Ordered by §6.5, so `OVER` warnings and biomarker-flagged nutrients lead.

**3. 추천** — elemental amount, suggested form with the reason that form was chosen, timing, interaction flags, citations.

**4. 참고: 2025 에너지 적정비율** — the official AMDR ranges (carbohydrate 50-65%, protein 10-20%, fat 15-30%) shown as reference, with the 2025 changes noted. Explicitly labelled as national guidance, not an assessment of this user, because the service does not know their energy intake.

Every number in blocks 2 and 3 is expandable to its trace step. Block 4 has no trace because nothing was computed — that asymmetry is the point.

---

## 10. Versioning, history, chat

```
reports(id, user_id, version, parent_id, profile_json, result_json, trace_json, created_at)
```

Nothing mutates. `입력 수정` prefills the intake form from `profile_json`, recomputes, and writes v2 with `parent_id = v1`. History lists revision chains, so a user can see how a recommendation changed when they corrected an input.

Chat binds to a specific report version. "Why did you recommend this" is always answerable because the exact trace that produced that answer is stored beside it.

This is what keeps the read-only chat from being a limitation: the user changes the recommendation by changing inputs and re-running the engine, never by arguing with the model.

---

## 11. Data model

> **Canonical schema lives in [erd.md](../../erd.md).** This section is a summary; when the two disagree, `erd.md` wins.

```
users(id, email, created_at)
magic_links(token, user_id, expires_at, used_at)
reports(id, user_id, version, parent_id, profile_json, result_json, trace_json, created_at)
chat_messages(id, report_id, role, content, created_at)

-- seeded, read-only at runtime
nutrients(nutrient_code, nutrient_ko, group_name, target_unit, ul_unit, synonyms_ko_label, ...)
kdri_bands(nutrient_code, sex, age_min, age_max, ri_base, ul_limit)
nutrient_limits(nutrient_code, applies_to_form, age_min, age_max, sex,
                ul_value, ul_unit, ul_basis, source)
nutrient_forms(nutrient_code, name_ko, elemental_pct, target_factor, ul_factor,
               absorption, gi_note, source)
nutrient_timing(nutrient_code, when, with_food, split_dose_above, rationale_ko, source)
interactions(nutrient_code, drug_class, drug_examples_ko, effect, action, severity, source)
energy_ratios(macronutrient, age_min, age_max, pct_min, pct_max, source, changed_2025)
```

Profiles live in the report snapshot rather than a separate table — a report must be reproducible from its own row.

---

## 12. Safety

| Condition | Behavior |
|---|---|
| Age < 19 | Refuse with reason, no numbers |
| Pregnancy or lactation flagged | Refuse with reason, refer to clinician |
| No band row for nutrient | `UNKNOWN`, no number |
| No sourced diet baseline | `UNKNOWN`, no number |
| Intake exceeds UL | `OVER`, reduction guidance, lead the report |
| Drug class absent from table | `평가되지 않음 — 약사와 상담하세요` |
| Every report | Non-diagnostic disclaimer |

The system declines to answer rather than guess. Every refusal states its reason.

---

## 13. Testing

**Exhaustive UL property test.** All 300 adult band rows: assert `current + recommend ≤ ul_limit` for every nutrient, band, and sex, across a grid of supplement-intake fixtures. Because adult scope is rectangular and fully enumerated, this is genuinely exhaustive rather than sampled.

**2025 range fixture.** Attachment 3 of the press release, transcribed to `tests/fixtures/kdri_2025_ranges.csv` — one row per nutrient with its published RNI/AI min and max. The test asserts every nutrient's range in our data matches, with a short allowlist of documented exceptions (rows the published range excludes, e.g. pregnancy deltas and lactation).

This is the check that caught magnesium M 15-18 = 410, a 2020 value surviving in a file labelled 2025. It runs on the full 1052 rows before scope filtering, so it guards bands MVP does not use. When the 2030 revision lands, this test is what tells us which rows moved.

**Golden tests.** The five worked examples in §6.7 as hand-computed assertions — magnesium elemental conversion, magnesium `OVER`, sex requirement, the niacin limit-row selection, and the folate DFE split. The last two exist because each was a silent wrong answer, not a crash.

**Seed assertions.** The §5.8 checks run as tests as well as at startup.

**Parser tests.** Fixed Korean label strings → expected structured output, LLM mocked. No test depends on live model output.

**Trace completeness.** Every number appearing in a report must be reachable from a trace step. Enforced by a test that walks the rendered result and asserts trace coverage — this is what keeps the why-chat honest as the engine grows.

---

## 14. Build phases

| Phase | Deliverable | Verifiable by |
|---|---|---|
| 0 | Seed + engine + tests. No UI, no LLM. | 300-case property test, 5 golden tests, 2025 range fixture |
| 1 | Curated content for 30 nutrients, all cited. Includes `nutrient_limits` (4 rows), `energy_ratios` (3 rows), and `target_factor` on folate forms. | Seed assertions; citation coverage check |
| 2 | API + intake wizard + report page | End-to-end for a manually-entered profile |
| 3 | Manual text parse + confirm screen | Parser tests |
| 4 | OCR path into the same confirm screen | Fixture photos |
| 5 | Sensitivity-driven follow-up questions | Swing ranking unit tests |
| 6 | Why-chat + trace rendering | Trace completeness test |
| 7 | Magic link auth + history + versioning | Revision chain test |

Phase 0 ships a testable dose calculator with nothing attached. If the arithmetic is wrong, that is discovered before any UI exists.

---

## 15. Known risks

**Diet baseline is the weakest link.** One national constant per nutrient means a vegan and a daily steak eater receive the same iron baseline. It is cited and defensible for MVP, and it is the first thing to get wrong. Upgrade path: the 5-8 question dietary questionnaire, adjusting the baseline per user. The `UNKNOWN` fallback (§6.4) contains the damage where KNHANES has no figure.

**Curated content is hand-authored.** `elemental_pct`, timing, and interaction rows are our judgment, not national guideline. Mitigated by mandatory per-row citations and by keeping them in files separate from vendor data, so any deviation is one greppable diff.

**Sodium is a reduction target, not a supplement.** It carries a CDRR value that the two-column vendor schema cannot represent. Displayed as status only, never recommended.

**Form-scoped limits will keep appearing.** Three of 30 nutrients already have them, and the 2025 revision added two of the three. `nutrient_limits` generalizes; the risk is a new form entering the parser without a matching limit row, which would silently fall through to the band default. Seed asserts every limit row is complete, and resolution step 4 (§5.3) returns "no limit" rather than a wrong one.

**The vendor CSVs are a near-perfect 2025 transcription, not a perfect one.** Magnesium M 15-18 = 410 is a confirmed 2020 survivor. It sits outside MVP scope, but the press release only publishes ranges — a stale value that happens to fall inside its nutrient's range would pass the fixture test undetected. **Full re-sourcing from mohw.go.kr or kns.or.kr is a pre-launch gate**, not a Phase 0 blocker. The range fixture reduces this risk; it does not close it.

**The press release is not the standards volume.** Every 2025 citation in this spec resolves to a 14-page announcement. Citations are honest about that. Before launch they should point at the published tables.

---

## 16. Future work

- Dietary questionnaire replacing the flat baseline constant
- Pediatric support with a normalized `life_stage` column
- Pregnancy and lactation, once lactation deltas are sourced
- Protein and energy, which would make `weight_kg` load-bearing
- Product catalog integration for brand-level recommendations
- MCP server exposing the dose engine
