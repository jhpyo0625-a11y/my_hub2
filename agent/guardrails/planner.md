# Planner 가드레일

계획 노드 계약. 존재하는 툴만, 의존 순서 준수.

## 하드 규칙 (수치 안전 경계, TB-1)
- LLM은 **tool_name·실행순서·parallel_group·재시도 전략·후속질문**만 결정한다.
- LLM은 **dose/RI/UL 등 어떤 수치 arg도 절대 생성하지 않는다.** args 값은 오직 state 파생 결정값(deterministic)만 사용한다.
- 이 경계는 `nodes/planner.py`의 `_repair_args`가 강제한다: LLM args는 `_contract_args` 결정값으로 전량 덮어쓰며, 수리 불가한(미지의) tool_name step은 LLM 수치 arg를 신뢰하지 않고 폐기한다.

가용 tool_name (9개): resolve_nutrient_codes, normalize_medical_data, fill_missing_profile, calculate_dynamic_ri, search_products, check_nutrient_interactions, validate_ul_guardrail, compute_intake_coverage, search_evidence.

## pre
- `normalized_data`와 `target_nutrients`가 state에 존재.

## post
- `execution_plan`은 비어있지 않은 list.
- 모든 step.tool_name ∈ 위 9개.
- 툴별 필수 args 존재:
  - resolve_nutrient_codes: names
  - normalize_medical_data: raw_lab_results
  - fill_missing_profile: age, gender, weight_kg, current_intake, target_nutrients
  - calculate_dynamic_ri: age, gender, weight_kg, target_nutrients
  - search_products: target_nutrients
  - check_nutrient_interactions: nutrient_list
  - validate_ul_guardrail: current_supps_intake, diet_estimated_intake, proposed_supps_intake, age, gender, weight_kg
  - compute_intake_coverage: intake, custom_ri
  - search_evidence: query, nutrient_code, k
- 순서 규칙 (두 툴이 모두 존재할 때만 step번호 비교):
  - **fill_missing_profile > resolve_nutrient_codes** (해석된 타깃 필요).
  - **calculate_dynamic_ri > resolve_nutrient_codes** (표준코드 필요).
  - **calculate_dynamic_ri > fill_missing_profile** (보정된 프로필 필요).
  - **validate_ul_guardrail > search_products** (UL 검증은 제품 검색 결과에 의존).
  - **compute_intake_coverage > calculate_dynamic_ri** (충족률은 맞춤 RI에 의존).
