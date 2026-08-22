# Aggregator 가드레일

취합 노드 계약. 숫자를 새로 만들거나 바꾸지 않는다(pass-through).

## pre
- `execution_results`가 state에 존재.

## post
- `aggregated_report`에 필수키: title, user_profile, calculated_target, ul_check, guidelines.
- **숫자 pass-through 동일**: calculated_target == executor의 calculate_dynamic_ri 결과, ul_check == executor의 validate_ul_guardrail 결과. (불일치 = 조작/환각 유입)
- guidelines는 list[str].
