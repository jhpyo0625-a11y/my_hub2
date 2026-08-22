# 통합 스키마 매트릭스

원천 엔티티 105개 + 런타임 관측 13개

필드가 많은 쪽을 뼈대로 삼되 **반대쪽 필드를 하나도 버리지 않습니다.**

## User  (6필드)

뼈대: `db:users` (5필드) · 원천 2곳

| 필드 | frontend2 | db | 판정 |
|---|---|---|---|
| `created_at` | — | `timestamp with time zone` | ★ 한쪽만 — 보존 필수 |
| `email` | `string` | — | ★ 한쪽만 — 보존 필수 |
| `id` | `string (optional)` | `character varying(100)` | 공통 |
| `name` | `string` | `character varying(100)` | 공통 |
| `pwd_hash` | — | `character varying(255)` | ★ 한쪽만 — 보존 필수 |
| `updated_at` | — | `timestamp with time zone` | ★ 한쪽만 — 보존 필수 |

## AnalysisInput  (19필드)

뼈대: `rt:normalized_data` (10필드) · 원천 4곳

| 필드 | frontend2 | rt | rt | mcp | 판정 |
|---|---|---|---|---|---|
| `age` | `string` | `integer` | `integer` | `integer *필수` | 공통 |
| `age_defaulted` | — | — | `boolean` | — | ★ 한쪽만 — 보존 필수 |
| `birth_date` | — | — | `null` | — | ★ 한쪽만 — 보존 필수 |
| `chronic` | `string[]` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `countMeal` | `boolean` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `current_intake` | — | — | — | `object (map→number)` | ★ 한쪽만 — 보존 필수 |
| `current_supplements` | — | `array(비어 있음)` | `array(비어 있음)` | — | 공통 |
| `date` | `string` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `exam` | `ExamValues` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `gender` | — | `string` | `string` | `string enum=['male', 'female'] *필수` | 공통 |
| `gender_defaulted` | — | — | `boolean` | — | ★ 한쪽만 — 보존 필수 |
| `is_pii` | — | — | `{name:boolean, birth_date:boolean}` | — | ★ 한쪽만 — 보존 필수 |
| `meds` | `Med[]` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `name` | `string` | `string` | `string` | — | 공통 |
| `products` | `Product[]` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `sex` | `''|'남성'|'여성'` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `target_nutrients` | — | — | — | `array of string` | ★ 한쪽만 — 보존 필수 |
| `units_normalized` | — | — | `boolean` | — | ★ 한쪽만 — 보존 필수 |
| `weight_kg` | — | `number` | `number` | `number` | 공통 |

## ExamValues  (33필드)

뼈대: `frontend2:ExamValues` (19필드) · 원천 4곳

| 필드 | frontend2 | frontend2 | rt | mcp | 판정 |
|---|---|---|---|---|---|
| `age` | — | `string` | — | — | ★ 한쪽만 — 보존 필수 |
| `alt` | `string (optional)` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `ast` | `string (optional)` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `chronic` | — | `string[]` | — | — | ★ 한쪽만 — 보존 필수 |
| `cr` | `string (optional)` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `cxr` | `string (optional)` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `date` | — | `string` | — | — | ★ 한쪽만 — 보존 필수 |
| `dbp` | `string (optional)` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `egfr` | `string (optional)` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `exam` | — | `ExamValues` | — | — | ★ 한쪽만 — 보존 필수 |
| `extracted_indicators` | — | — | `{}` | — | ★ 한쪽만 — 보존 필수 |
| `ggt` | `string (optional)` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `glu` | `string (optional)` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `groups` | — | `string[]` | — | — | ★ 한쪽만 — 보존 필수 |
| `hb` | `string (optional)` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `hdl` | `string (optional)` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `height` | `string (optional)` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `ldl` | `string (optional)` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `name` | — | `string` | — | — | ★ 한쪽만 — 보존 필수 |
| `results` | — | — | — | `array *필수` | ★ 한쪽만 — 보존 필수 |
| `results[].flag` | — | — | — | `string enum=['low', 'normal', 'high']` | ★ 한쪽만 — 보존 필수 |
| `results[].test_name` | — | — | — | `string` | ★ 한쪽만 — 보존 필수 |
| `results[].unit` | — | — | — | `string` | ★ 한쪽만 — 보존 필수 |
| `results[].value` | — | — | — | `number` | ★ 한쪽만 — 보존 필수 |
| `sbp` | `string (optional)` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `sex` | — | `string` | — | — | ★ 한쪽만 — 보존 필수 |
| `source` | — | `'demo'|'model'` | — | — | ★ 한쪽만 — 보존 필수 |
| `tc` | `string (optional)` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `tg` | `string (optional)` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `tscore` | `string (optional)` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `upro` | `string (optional)` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `waist` | `string (optional)` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `weight` | `string (optional)` | — | — | — | ★ 한쪽만 — 보존 필수 |

## Nutrient  (42필드)

뼈대: `frontend2:Nutrient` (19필드) · 원천 6곳

| 필드 | frontend2 | frontend2 | mcp | mcp | db | db | 판정 |
|---|---|---|---|---|---|---|---|
| `age_max` | — | — | — | — | `integer` | — | ★ 한쪽만 — 보존 필수 |
| `age_min` | — | — | — | — | `integer` | — | ★ 한쪽만 — 보존 필수 |
| `alias` | — | `list` | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `bar` | `NutrientBar` | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `basis` | `string` | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `caption` | `string` | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `coverage` | — | — | — | `object (map→object) *필수` | — | — | ★ 한쪽만 — 보존 필수 |
| `custom_ri` | — | — | `object (map→object) *필수` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `gauge` | `NutrientGauge` | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `gender` | — | — | — | — | `character varying(10)` | — | ★ 한쪽만 — 보존 필수 |
| `group_name` | — | — | — | — | — | `character varying(50)` | ★ 한쪽만 — 보존 필수 |
| `hasStd` | `boolean` | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `has_ai` | — | — | — | — | — | `boolean nullable` | ★ 한쪽만 — 보존 필수 |
| `has_cdrr` | — | — | — | — | — | `boolean nullable` | ★ 한쪽만 — 보존 필수 |
| `has_ear` | — | — | — | — | — | `boolean nullable` | ★ 한쪽만 — 보존 필수 |
| `has_rni` | — | — | — | — | — | `boolean nullable` | ★ 한쪽만 — 보존 필수 |
| `has_ul` | — | — | — | — | — | `boolean nullable` | ★ 한쪽만 — 보존 필수 |
| `id` | — | — | — | — | `integer` | — | ★ 한쪽만 — 보존 필수 |
| `is_weight_scaled` | — | — | — | — | `boolean nullable` | — | ★ 한쪽만 — 보존 필수 |
| `iu` | — | `float` | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `kdri_unit` | — | — | — | — | — | `character varying(30)` | ★ 한쪽만 — 보존 필수 |
| `kdri_version` | — | — | — | — | — | `integer nullable` | ★ 한쪽만 — 보존 필수 |
| `key` | `string` | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `level` | `Level` | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `meal` | `number` | `int` | — | — | — | — | 공통 |
| `name` | `string` | `str` | — | — | — | — | 공통 |
| `note` | `NutrientNote` | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `nutrient_code` | — | — | — | — | `character varying(50)` | `character varying(50)` | 공통 |
| `nutrient_ko` | — | — | — | — | — | `character varying(100)` | ★ 한쪽만 — 보존 필수 |
| `rda` | `number|null` | `int` | — | — | — | — | 공통 |
| `ri_base` | — | — | — | — | `numeric nullable` | — | ★ 한쪽만 — 보존 필수 |
| `sources` | `string[]` | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `supp` | `number` | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `synonyms_ko_label` | — | — | — | — | — | `text nullable` | ★ 한쪽만 — 보존 필수 |
| `total` | `number` | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `ul` | `number|null` | `int` | — | — | — | — | 공통 |
| `ulAmount` | `number` | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `ulSuppOnly` | `boolean` | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `ul_basis` | — | `str` | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `ul_limit` | — | — | — | — | `numeric nullable` | — | ★ 한쪽만 — 보존 필수 |
| `unit` | `string` | `str` | — | — | — | — | 공통 |
| `unmapped` | `string[]` | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |

## Product  (15필드)

뼈대: `mcp:search_products.output` (6필드) · 원천 4곳

| 필드 | frontend2 | frontend2 | mcp | db | 판정 |
|---|---|---|---|---|---|
| `amount` | — | `number|string` | — | — | ★ 한쪽만 — 보존 필수 |
| `amount_per_serving` | — | — | — | `numeric` | ★ 한쪽만 — 보존 필수 |
| `id` | — | — | — | `integer` | ★ 한쪽만 — 보존 필수 |
| `items` | `ProductItem[]` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `name` | `string` | `string` | — | — | 공통 |
| `nutrient_code` | — | — | — | `character varying(50)` | ★ 한쪽만 — 보존 필수 |
| `product_id` | — | — | — | `character varying(50)` | ★ 한쪽만 — 보존 필수 |
| `product_name` | — | — | — | `character varying(255)` | ★ 한쪽만 — 보존 필수 |
| `products` | — | — | `array *필수` | — | ★ 한쪽만 — 보존 필수 |
| `products[].brand` | — | — | `string|null` | — | ★ 한쪽만 — 보존 필수 |
| `products[].form` | — | — | `string|null` | — | ★ 한쪽만 — 보존 필수 |
| `products[].label_id` | — | — | `integer` | — | ★ 한쪽만 — 보존 필수 |
| `products[].nutrients` | — | — | `object (map→number)` | — | ★ 한쪽만 — 보존 필수 |
| `products[].product_name` | — | — | `string` | — | ★ 한쪽만 — 보존 필수 |
| `unit` | — | `string` | — | `character varying(20)` | 공통 |

## Issue  (17필드)

뼈대: `mcp:validate_ul_guardrail.output` (7필드) · 원천 4곳

| 필드 | frontend2 | frontend2 | mcp | mcp | 판정 |
|---|---|---|---|---|---|
| `approved_recommendations` | — | — | `array of object *필수` | — | ★ 한쪽만 — 보존 필수 |
| `cautions` | — | — | — | `array of string *필수` | ★ 한쪽만 — 보존 필수 |
| `conflicts_found` | — | — | — | `boolean *필수` | ★ 한쪽만 — 보존 필수 |
| `is_safe` | — | — | `boolean *필수` | — | ★ 한쪽만 — 보존 필수 |
| `kind` | `string` | `str` | — | — | 공통 |
| `med` | `string (optional)` | `list` | — | — | 공통 |
| `nut` | — | `str` | — | — | ★ 한쪽만 — 보존 필수 |
| `text` | `string` | `str` | — | — | 공통 |
| `time_separated_schedule` | — | — | — | `object *필수` | ★ 한쪽만 — 보존 필수 |
| `time_separated_schedule.evening_PM` | — | — | — | `array of string` | ★ 한쪽만 — 보존 필수 |
| `time_separated_schedule.morning_AM` | — | — | — | `array of string` | ★ 한쪽만 — 보존 필수 |
| `tone` | `Tone` | `str` | — | — | 공통 |
| `ul_violations` | — | — | `array *필수` | — | ★ 한쪽만 — 보존 필수 |
| `ul_violations[].nutrient` | — | — | `string` | — | ★ 한쪽만 — 보존 필수 |
| `ul_violations[].status` | — | — | `string const=EXCEEDED` | — | ★ 한쪽만 — 보존 필수 |
| `ul_violations[].total_intake` | — | — | `number` | — | ★ 한쪽만 — 보존 필수 |
| `ul_violations[].ul_limit` | — | — | `number` | — | ★ 한쪽만 — 보존 필수 |

## Report  (30필드)

뼈대: `frontend2:Report` (12필드) · 원천 4곳

| 필드 | frontend2 | rt | rt | db | 판정 |
|---|---|---|---|---|---|
| `badges` | `Badge[]` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `calculated_target` | — | `{custom_ri:{vitamin_d:object, calcium:object, magnesium:object}}` | — | — | ★ 한쪽만 — 보존 필수 |
| `cols` | `number` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `compliance_checked` | — | — | `boolean` | — | ★ 한쪽만 — 보존 필수 |
| `created_at` | — | — | — | `timestamp without time zone nullable` | ★ 한쪽만 — 보존 필수 |
| `disclaimer` | — | — | `string` | — | ★ 한쪽만 — 보존 필수 |
| `exam` | `ExamModel` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `failed_items` | — | `array(비어 있음)` | — | — | ★ 한쪽만 — 보존 필수 |
| `guidelines` | — | `array(비어 있음)` | — | — | ★ 한쪽만 — 보존 필수 |
| `hasSupp` | `boolean` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `health_indicators` | — | `{}` | — | — | ★ 한쪽만 — 보존 필수 |
| `html` | — | — | `string` | — | ★ 한쪽만 — 보존 필수 |
| `id` | — | — | — | `integer` | ★ 한쪽만 — 보존 필수 |
| `input` | `AnalysisInput` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `issues` | `Issue[]` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `mealOnly` | `boolean` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `meta` | `ReportMeta` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `nutrients` | `Nutrient[]` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `output_report` | — | — | — | `jsonb` | ★ 한쪽만 — 보존 필수 |
| `partial_failure` | — | — | `boolean` | — | ★ 한쪽만 — 보존 필수 |
| `products` | — | `array(비어 있음)` | — | — | ★ 한쪽만 — 보존 필수 |
| `recommend` | `Recommend|null` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `summary` | `Summary` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `timing_guidance` | — | `{conflicts_found:boolean, time_separated_schedule:{morning_AM:array<string>, evening_PM:array<string>}, cautions:array<string>}` | — | — | ★ 한쪽만 — 보존 필수 |
| `title` | — | `string` | — | `character varying(255)` | 공통 |
| `ul_check` | — | `{is_safe:boolean, ul_violations:array(비어 있음), approved_recommendations:array(비어 있음)}` | — | — | ★ 한쪽만 — 보존 필수 |
| `user_health_preset_id` | — | — | — | `jsonb` | ★ 한쪽만 — 보존 필수 |
| `user_id` | — | — | — | `character varying(50)` | ★ 한쪽만 — 보존 필수 |
| `user_profile` | — | `{units_normalized:boolean, name:string, birth_date:null, age:integer, gender:string, weight_kg:number…}` | `{units_normalized:boolean, name:string, birth_date:null, age:integer, gender:string, weight_kg:number…}` | — | 공통 |
| `worst` | `Level` | — | — | — | ★ 한쪽만 — 보존 필수 |

## ExamJudgement  (17필드)

뼈대: `frontend2:ExamModel` (5필드) · 원천 5곳

| 필드 | frontend2 | frontend2 | frontend2 | frontend2 | frontend2 | 판정 |
|---|---|---|---|---|---|---|
| `abnormal` | `ExamRow[]` | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `advice` | — | — | — | `string (optional)` | — | ★ 한쪽만 — 보존 필수 |
| `code` | — | — | — | `JudgeCode` | — | ★ 한쪽만 — 보존 필수 |
| `desc` | — | — | — | — | `string` | ★ 한쪽만 — 보존 필수 |
| `filled` | `number` | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `group` | — | — | `string` | — | — | ★ 한쪽만 — 보존 필수 |
| `groups` | `ExamGroup[]` | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `judge` | — | `ExamJudge` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `key` | — | `string` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `label` | — | — | — | — | `string` | ★ 한쪽만 — 보존 필수 |
| `name` | — | `string` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `overall` | `ExamOverall` | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `ref` | — | `string` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `rows` | `ExamRow[]` | — | `ExamRow[]` | — | — | 공통 |
| `text` | — | — | — | `string` | — | ★ 한쪽만 — 보존 필수 |
| `tone` | — | — | — | `Tone` | `Tone` | 공통 |
| `value` | — | `string` | — | — | — | ★ 한쪽만 — 보존 필수 |

## Plan  (16필드)

뼈대: `agent:PlanStep` (6필드) · 원천 4곳

| 필드 | agent | agent | rt | rt | 판정 |
|---|---|---|---|---|---|
| `[].args` | — | — | `{age:integer, gender:string, weight_kg:number, target_nutrients:array<string>} | {current_supps_intake:{}, diet_estimated_intake:{}, proposed_supps_intake:{}, age:integer, gender:string, weight_kg:number} | {nutrient_list:array<string>} | {target_nutrients:array<string>}` | — | ★ 한쪽만 — 보존 필수 |
| `[].description` | — | — | `string` | — | ★ 한쪽만 — 보존 필수 |
| `[].output` | — | — | — | `{conflicts_found:boolean, time_separated_schedule:{morning_AM:array<string>, evening_PM:array<string>}, cautions:array<string>} | {custom_ri:{vitamin_d:object, calcium:object, magnesium:object}} | {is_safe:boolean, ul_violations:array(비어 있음), approved_recommendations:array(비어 있음)} | {products:array(비어 있음)}` | ★ 한쪽만 — 보존 필수 |
| `[].parallel_group` | — | — | `integer | null` | — | ★ 한쪽만 — 보존 필수 |
| `[].result` | — | — | — | `{conflicts_found:boolean, time_separated_schedule:{morning_AM:array<string>, evening_PM:array<string>}, cautions:array<string>} | {custom_ri:{vitamin_d:object, calcium:object, magnesium:object}} | {is_safe:boolean, ul_violations:array(비어 있음), approved_recommendations:array(비어 있음)} | {products:array(비어 있음)}` | ★ 한쪽만 — 보존 필수 |
| `[].status` | — | — | — | `string` | ★ 한쪽만 — 보존 필수 |
| `[].step` | — | — | `integer` | `integer` | 공통 |
| `[].task_name` | — | — | `string` | `string` | 공통 |
| `[].tool_name` | — | — | `string` | `string` | 공통 |
| `args` | `dict[str, Any]` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `description` | `str` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `parallel_group` | `int | None` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `step` | `int` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `steps` | — | `list[PlanStep]` | — | — | ★ 한쪽만 — 보존 필수 |
| `task_name` | `str` | — | — | — | ★ 한쪽만 — 보존 필수 |
| `tool_name` | `ToolName` | — | — | — | ★ 한쪽만 — 보존 필수 |

## PipelineState  (15필드)

뼈대: `agent:State` (14필드) · 원천 7곳

| 필드 | agent | rt | rt | rt | rt | rt | rt | 판정 |
|---|---|---|---|---|---|---|---|---|
| `(스칼라)` | — | `string` | `string` | `integer` | `array<string>` | `array(비어 있음)` | `string` | 공통 |
| `aggregated_report` | `Dict[str, Any]` | — | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `execution_plan` | `List[Dict[str, Any]]` | — | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `execution_results` | `List[Dict[str, Any]]` | — | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `failed_items` | `List[Dict[str, Any]]` | — | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `final_report` | `Dict[str, Any]` | — | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `normalized_data` | `Dict[str, Any]` | — | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `ocr_result` | `Dict[str, Any]` | — | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `ocr_text` | `str` | — | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `rag_context` | `List[Dict[str, Any]]` | — | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `retry_count` | `int` | — | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `review_feedback` | `str` | — | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `review_status` | `Literal['pass', 'reject_to_executor', 'reject_to_planner']` | — | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `target_nutrients` | `List[str]` | — | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |
| `user_input` | `Dict[str, Any]` | — | — | — | — | — | — | ★ 한쪽만 — 보존 필수 |

## 잔여 — 대응되는 짝이 없는 엔티티

다른 원천에 대응이 없으므로 **병합 대상이 아닙니다.** 충돌 가능성이 없어 그대로 둡니다.

- **agent** (22) — AggregatedReport, CoverageStatus, ExamValues, FinalReport, Gender, InteractionResult, JudgeCode, LabFlag, LabResult, Level, NormalizedData, NutrientCoverage, NutrientTarget, ResponseStatus, ReviewStatus, SessionUser, TimeSeparatedSchedule, Tone, ToolName, UlCheckResult, UlViolation, UserInput
- **agent-node** (4) — aggregated_report, final_report, normalized_data, ocr_result
- **db** (1) — user_health_presets
- **frontend2** (27) — ApiEnvelope, Badge, Bootstrap, BrandCopy, CHRONIC, CoverageStatus, Gender, JudgeCode, LEVEL_RANK, LabFlag, Level, Med, NutrientBar, NutrientGauge, NutrientNote, Recommend, RecommendItem, ReportInfo, ReportListItem, ReportMeta, ResponseStatus, Sex, Summary, TimeSeparatedSchedule, Tone, UNITS, UlViolation
- **mcp** (11) — calculate_dynamic_ri.input, check_nutrient_interactions.input, compute_intake_coverage.input, fill_missing_profile.output, normalize_medical_data.input, resolve_nutrient_codes.input, resolve_nutrient_codes.output, search_evidence.input, search_evidence.output, search_products.input, validate_ul_guardrail.input
- **mcp-impl** (9) — calculate_dynamic_ri.signature, check_nutrient_interactions.signature, compute_intake_coverage.signature, fill_missing_profile.signature, normalize_medical_data.signature, resolve_nutrient_codes.signature, search_evidence.signature, search_products.signature, validate_ul_guardrail.signature

## 요약

| | |
|---|---|
| 병합한 개념 | 10개 |
| 병합 후 필드 | 210개 |
| 짝 없는 엔티티 | 74개 |
| **미분류 잔여** | **0개** |
