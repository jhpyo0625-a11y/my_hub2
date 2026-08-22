# Executor 가드레일

실행 노드 계약. LLM이 숫자를 만들지 않는다는 규칙의 출력 경계 강제.

## pre
- `execution_plan`이 state에 존재.

## post
- `execution_results`는 비어있지 않은 list.
- 각 항목 status ∈ {success, error}.
- calculate_dynamic_ri 성공 결과의 custom_ri 값에 null/0 누출 없음 (매칭 없는 코드는 생략돼야 하며 0으로 처방하지 않음).
