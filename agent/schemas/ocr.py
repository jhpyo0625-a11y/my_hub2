# -*- coding: utf-8 -*-
"""비전 OCR 구조화 출력 스키마.

value/unit는 STR(verbatim) — `음성(-)`, 범위, 정확한 자릿수를 원문 그대로 보존.
숫자 파싱/정규화는 하류(normalizer, normalize_medical_data 툴)의 책임.
"""
from pydantic import BaseModel, Field


class OcrIndicator(BaseModel):
    name: str = Field(description="항목명 (예: 비타민 D, 칼슘, 중성지방)")
    value: str = Field(description="값 원문 그대로 (예: '12.3', '음성(-)', '10-20')")
    unit: str = Field(description="단위 원문 그대로 (예: 'ng/mL', '없으면 빈 문자열')")


class OcrExtraction(BaseModel):
    raw_text: str = Field(description="이미지 전체 텍스트를 원문 그대로 전사")
    indicators: list[OcrIndicator] = Field(
        default_factory=list, description="추출한 항목 목록"
    )
