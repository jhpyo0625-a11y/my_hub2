from schemas.state import State
from services.ocr import run_ocr_pipeline


def input_normalization_node(state: State) -> State:
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
        state["ocr_result"] = {
            "extracted_indicators": {}
        }
        state["ocr_text"] = ""

    state["normalized_data"] = {
        "masked": True,
        "units_normalized": True,
        "name": user_input.get("name") or "익명",
        "age": user_input.get("age") or 30,
        "weight_kg": user_input.get("weight_kg") or 60.0,
        "current_supplements": user_input.get(
            "current_supplements",
            []
        ),
    }

    return state
