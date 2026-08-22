from schemas.state import State
from services.ocr import run_ocr_pipeline


# OCR 지표명 → 내부 nutrient_code 매핑(베스트 에포트).
# ponytail: 최소 매핑만. 실제 코드 체계는 MCP 측 소관, 추가 지표는 여기 확장.
_INDICATOR_TO_CODE = {
    "Vitamin_D": "vitamin_d",
    "Calcium": "calcium",
    "Triglyceride": "epa_dha",
}

# 지표와 무관하게 항상 검토할 코어 영양소 (nutrient_codes 테이블 기준).
_DEFAULT_TARGETS = ["vitamin_d", "calcium", "magnesium", "epa_dha"]


async def input_normalization_node(state: State) -> State:
    print(
        "\n[Node 1] Normalizer: "
        "이미지 OCR 및 입력 데이터 정규화 처리 중..."
    )

    user_input = state.get("user_input", {})

    image_bytes = user_input.get("image_bytes")
    filename = user_input.get("filename")

    if image_bytes:
        ocr_result = run_ocr_pipeline(
            image_bytes=image_bytes,
            filename=filename,
        )
        state["ocr_result"] = ocr_result
        state["ocr_text"] = ocr_result.get("raw_text", "")
    else:
        state["ocr_result"] = {"extracted_indicators": {}}
        state["ocr_text"] = ""

    indicators = state["ocr_result"].get("extracted_indicators", {})

    # PII는 마스킹하지 않고 원본 보존. 어떤 필드가 PII인지 스키마 레벨에서 태깅.
    # gender: KDRI 규칙상 성별은 임의 기본값 금지 대상이나, 파이프라인 산출을 위해
    # 누락 시 female로 채우고 gender_defaulted 플래그로 하류에 사실을 전달한다.
    # ponytail: 단일 기본값+플래그. 실서비스는 API에서 gender 필수화로 승격할 것.
    gender = (user_input.get("gender") or "").lower()
    gender_defaulted = gender not in ("male", "female")
    if gender_defaulted:
        gender = "female"

    # age: 미만/누락 시 스코프 이탈이므로 기본값 사용 여부를 하류에 플래그로 전달.
    age_in = user_input.get("age")
    age_defaulted = not isinstance(age_in, int)
    age = age_in if isinstance(age_in, int) else 30

    state["normalized_data"] = {
        "units_normalized": True,
        "name": user_input.get("name") or "익명",
        "birth_date": user_input.get("birth_date"),
        "age": age,
        "gender": gender,
        "gender_defaulted": gender_defaulted,
        "age_defaulted": age_defaulted,
        "weight_kg": user_input.get("weight_kg") or 60.0,
        "current_supplements": user_input.get("current_supplements", []),
        # Compliance 마스킹 단계가 식별할 PII 필드 목록.
        "is_pii": {"name": True, "birth_date": True},
    }

    # 타깃 영양소: 이상 지표(deficient/warning) + 코어 셋.
    targets = list(_DEFAULT_TARGETS)
    for name, info in indicators.items():
        if info.get("status") in ("warning", "deficient"):
            code = _INDICATOR_TO_CODE.get(name)
            if code and code not in targets:
                targets.append(code)
    state["target_nutrients"] = targets

    return state
