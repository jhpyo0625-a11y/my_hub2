from typing import TypedDict, List, Dict, Any, Literal


class State(TypedDict, total=False):
    # User Input
    user_input: Dict[str, Any]

    # OCR
    ocr_text: str
    ocr_result: Dict[str, Any]

    # Normalization (PII 원본 보존 + is_pii 태깅. 마스킹은 Compliance 단계에서만)
    raw_lab_results: List[Dict[str, Any]]
    normalized_data: Dict[str, Any]
    target_nutrients: List[str]

    # RAG (Aggregator 단계에서 채움)
    rag_context: List[Dict[str, Any]]

    # Planning / Execution
    execution_plan: List[Dict[str, Any]]
    execution_results: List[Dict[str, Any]]
    # 3회 재시도 소진 후 확정된 부분 실패 항목
    failed_items: List[Dict[str, Any]]

    # Review
    review_status: Literal[
        "pass",
        "reject_to_executor",
        "reject_to_planner"
    ]
    review_feedback: str

    # Report
    aggregated_report: Dict[str, Any]
    final_report: Dict[str, Any]

    # Retry
    retry_count: int
