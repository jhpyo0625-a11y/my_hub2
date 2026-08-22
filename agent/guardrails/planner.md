# Planner 가드레일

계획 노드 계약. 존재하는 툴만, 의존 순서 준수.

가용 tool_name: calculate_dynamic_ri, validate_ul_guardrail, check_nutrient_interactions, search_products.

## pre
- `normalized_data`와 `target_nutrients`가 state에 존재.

## post
- `execution_plan`은 비어있지 않은 list.
- 모든 step.tool_name ∈ 위 4개.
- 툴별 필수 args 존재:
  - calculate_dynamic_ri: age, gender, weight_kg, target_nutrients
  - validate_ul_guardrail: current_supps_intake, diet_estimated_intake, proposed_supps_intake, age, gender, weight_kg
  - check_nutrient_interactions: nutrient_list
  - search_products: target_nutrients
- **validate_ul_guardrail의 step번호 > search_products의 step번호** (UL 검증은 제품 검색 결과에 의존).
