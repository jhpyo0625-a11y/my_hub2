# Normalizer 가드레일

정규화 노드 계약. established rule: 성인 19세 이상만, 성별 필수(기본값 금지).

## pre (전제조건)
- `user_input`이 state에 존재.

## post (이탈이면 flag)
- `normalized_data.age`는 int이고 **19 이상**. (미만/누락 → 스코프 이탈)
- `age_defaulted`가 True이면 스코프 이탈로 flag. (age 누락 시 임의 기본값을 채워서는 안 됨)
- `normalized_data.gender` ∈ {male, female}이고 `gender_defaulted`가 False. (성별은 기본값으로 채우면 안 됨)
- `normalized_data.is_pii` 태그 존재. (Compliance 마스킹이 참조)
- `target_nutrients`는 비어있지 않은 list[str].
- OCR은 전사(item명/value/unit)만 수행하고 임상 status나 허구 값을 만들지 않는다; 실패 시 빈 추출.
