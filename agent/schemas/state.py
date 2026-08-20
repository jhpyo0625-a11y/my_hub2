from typing import TypedDict, List, Dict, Any, Literal


class State(TypedDict, total=False):
    # User Input
    user_input: Dict[str, Any]

    # OCR
    ocr_text: str
    ocr_result: Dict[str, Any]

    # Normalization
    normalized_data: Dict[str, Any]

    # RAG
    rag_context: List[Dict[str, Any]]

    # Planning / Execution
    execution_plan: List[Dict[str, Any]]
    execution_results: List[Dict[str, Any]]

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
