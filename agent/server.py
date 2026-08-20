from typing import Optional

from fastapi import (
    FastAPI,
    HTTPException,
    UploadFile,
    File,
    Form,
)

from schemas.state import State
from graph.workflow import graph


app = FastAPI(
    title="AI 영양제 추천 서비스 API",
    description=(
        "멀티 에이전트 오케스트레이션 및 "
        "MCP 툴 기반 정밀 영양 추천 API"
    ),
    version="1.2.0",
)


@app.post(
    "/api/v1/recommend",
    summary="검진표 이미지 기반 개인 맞춤 영양 추천 생성",
)
async def recommend_nutrition(
    file: Optional[UploadFile] = File(
        None,
        description="검진표 이미지 또는 PDF 파일",
    ),
    name: Optional[str] = Form(
        None,
        description="사용자 이름",
    ),
    age: Optional[int] = Form(
        None,
        description="나이",
    ),
    weight_kg: Optional[float] = Form(
        None,
        description="체중 (kg)",
    ),
):
    try:
        image_bytes = None
        filename = None

        if file:
            image_bytes = await file.read()
            filename = file.filename

        user_input = {
            "name": name,
            "age": age,
            "weight_kg": weight_kg,
            "image_bytes": image_bytes,
            "filename": filename,
            "current_supplements": [],
        }

        initial_state: State = {
            "user_input": user_input,
            "retry_count": 0,
        }

        final_state = graph.invoke(
            initial_state
        )

        return {
            "status": "success",
            "data": final_state.get(
                "final_report",
                {},
            ),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=(
                f"파이프라인 실행 중 오류 발생: {str(e)}"
            ),
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
