import base64
import json
from typing import Dict, Any

import config
from prompts.ocr_prompt import OCR_SYSTEM_PROMPT
from schemas.ocr import OcrExtraction


def _mime(filename: str) -> str:
    ext = (filename or "").lower().rsplit(".", 1)[-1]
    if ext in ("jpg", "jpeg"):
        return "image/jpeg"
    return "image/png"  # png 및 미지 확장자 기본값


def _blank(reason: str) -> Dict[str, Any]:
    """빈 추출 폴백. status·허구 값 없음. 실패는 정직하게 빈 결과로 전한다."""
    print(f"[OCR] 빈 추출 폴백 사용 (사유: {reason})")
    return {"raw_text": "", "extracted_indicators": {}}


def _to_return_shape(ext: OcrExtraction) -> Dict[str, Any]:
    """OcrExtraction → normalizer가 소비하는 {name: {value, unit}} dict.

    중복 항목명은 last-wins. value/unit은 문자열 원문 그대로 유지.
    """
    indicators: Dict[str, Dict[str, str]] = {}
    for ind in ext.indicators:
        name = (ind.name or "").strip()
        if not name:
            continue
        indicators[name] = {"value": ind.value, "unit": ind.unit}
    return {"raw_text": ext.raw_text or "", "extracted_indicators": indicators}


def run_ocr_pipeline(image_bytes: bytes, filename: str) -> Dict[str, Any]:
    """비전 OCR 파이프라인. OpenAI 비전 모델이 이미지 텍스트/숫자를 전사한다.

    키+이미지 있으면 실호출, 없거나 실패하면 빈 추출 폴백(허구 값 없음).
    반환 shape: {raw_text: str, extracted_indicators: {name: {value: str, unit: str}}}.
    """
    if not config.OPENAI_API_KEY:
        return _blank("OPENAI_API_KEY 없음")
    if not image_bytes:
        return _blank("이미지 없음")

    try:
        from langchain_openai import ChatOpenAI

        data_uri = (
            f"data:{_mime(filename)};base64,"
            + base64.b64encode(image_bytes).decode("ascii")
        )
        # _llm_plan과 동일한 model/base_url/key 구성. function_calling: 프록시가
        # strict json_schema를 거부할 수 있어 완화된 tool-calling 모드 사용.
        llm = ChatOpenAI(
            model=config.OPENAI_MODEL,
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
            temperature=0,
        )
        human = [
            {
                "type": "text",
                "text": "이 이미지의 모든 텍스트와 검사 항목(항목명·값·단위)을 "
                        "누락 없이 원문 그대로 추출하라.",
            },
            {"type": "image_url", "image_url": {"url": data_uri}},
        ]
        messages = [("system", OCR_SYSTEM_PROMPT), ("human", human)]

        try:
            structured = llm.with_structured_output(
                OcrExtraction, method="function_calling"
            )
            result: OcrExtraction = structured.invoke(messages)
            return _to_return_shape(result)
        except Exception as se:  # noqa: BLE001
            # 프록시가 structured output(tool-calling)을 거부하면 평문 JSON으로 재시도.
            print(f"[OCR] structured output 실패, 평문 JSON 재시도: {se}")
            raw = llm.invoke(
                [
                    ("system", OCR_SYSTEM_PROMPT
                     + '\n\n반드시 다음 JSON만 출력하라(마크다운·코드펜스 금지): '
                       '{"raw_text": "...", "indicators": '
                       '[{"name": "...", "value": "...", "unit": "..."}]}'),
                    ("human", human),
                ]
            )
            text = getattr(raw, "content", raw)
            if isinstance(text, list):  # content block 리스트일 수 있음
                text = "".join(b.get("text", "") for b in text if isinstance(b, dict))
            return _to_return_shape(OcrExtraction.model_validate(json.loads(text)))
    except Exception as e:  # noqa: BLE001 - 어떤 실패든 정직하게 빈 추출로 강등
        return _blank(f"OCR 실패: {e}")
