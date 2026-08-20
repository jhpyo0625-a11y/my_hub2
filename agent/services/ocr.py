from typing import Dict, Any


def run_ocr_pipeline(
    image_bytes: bytes,
    filename: str
) -> Dict[str, Any]:
    """
    OCR 처리 및 PII 비식별화 파이프라인

    TODO:
    - Upstage Document AI
    - PII masking
    - 의료 데이터 parsing
    - 단위 정규화
    """

    print(
        f"[OCR] 파일({filename}, "
        f"{len(image_bytes)} bytes) 파싱 및 PII 비식별화 진행 중..."
    )

    parsed_medical_data = {
        "pii_masked": True,
        "raw_text": (
            "혈중 비타민 D: 12.3 ng/mL, "
            "혈중 칼슘: 9.5 mg/dL, "
            "중성지방: 180 mg/dL"
        ),
        "extracted_indicators": {
            "Vitamin_D": {
                "value": 12.3,
                "unit": "ng/mL",
                "status": "deficient",
            },
            "Calcium": {
                "value": 9.5,
                "unit": "mg/dL",
                "status": "normal",
            },
            "Triglyceride": {
                "value": 180,
                "unit": "mg/dL",
                "status": "warning",
            },
        },
    }

    return parsed_medical_data
