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

from guardrails.harness import GuardViolation
from nodes.compliance import DISCLAIMER
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="AI 영양제 추천 서비스 API",
    description=(
        "멀티 에이전트 오케스트레이션 및 "
        "MCP 툴 기반 정밀 영양 추천 API"
    ),
    version="1.2.0",
)



# ============================================================
# 공통 응답 형식
# ============================================================

def success_response(data=None):
    return {
        "status": "success",
        "message": "",
        "data": data if data is not None else {},
    }


def fail_response(error):
    return {
        "status": "fail",
        "message": str(error),
        "data": {},
    }


# ============================================================
# 회원가입 API
# ============================================================

@app.post(
    "/api/v1/signup",
    summary="사용자 회원가입"
)
async def signup(
    id: str = Form(...),
    pwd: str = Form(...),
    name: str = Form(...),
):
    try:
        # 필수값 검증
        if not id.strip():
            raise ValueError("아이디를 입력해주세요.")

        if not pwd.strip():
            raise ValueError("비밀번호를 입력해주세요.")

        if not name.strip():
            raise ValueError("이름을 입력해주세요.")

        # 회원정보 조회 (db_helper 이용, executor 참고할 것)
        users = {}

        # 이미 가입된 사용자 확인
        if id in users:
            raise ValueError("이미 존재하는 아이디입니다.")

        # 회원 저장
        users[id] = {
            "id": id,
            "pwd": pwd,
            "name": name,
        }

        return success_response(
            {
                "user": {
                    "id": id,
                    "name": name,
                }
            }
        )

    except Exception as e:
        return fail_response(e)


# ============================================================
# 로그인 API
# ============================================================

@app.post(
    "/api/v1/login",
    summary="사용자 로그인"
)
async def login(
    id: str = Form(...),
    pwd: str = Form(...),
):
    try:
        # 사용자 존재 여부 확인 (db_helper 이용, executor 참고할 것)
        user = {}

        if user is None:
            raise ValueError(
                "아이디 또는 비밀번호가 올바르지 않습니다."
            )

        # 비밀번호 확인
        if user["pwd"] != pwd:
            raise ValueError(
                "아이디 또는 비밀번호가 올바르지 않습니다."
            )

        return success_response(
            {
                "user": {
                    "id": user["id"],
                    "name": user["name"],
                }
            }
        )

    except Exception as e:
        return fail_response(e)


# ============================================================
# 영양제 추천 API
# ============================================================

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
    birth_date: Optional[str] = Form(
        None,
        description="생년월일 (YYYY-MM-DD)",
    ),
    age: Optional[int] = Form(
        None,
        description="나이",
    ),
    gender: Optional[str] = Form(
        None,
        description="성별 (male/female)",
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
            "birth_date": birth_date,
            "age": age,
            "gender": gender,
            "weight_kg": weight_kg,
            "image_bytes": image_bytes,
            "filename": filename,
            "current_supplements": [],
        }

        initial_state: State = {
            "user_input": user_input,
            "retry_count": 0,
        }

        # 노드가 async이므로 ainvoke 사용.
        try:
            final_state = await graph.ainvoke(initial_state)
        except GuardViolation as gv:
            print(f"[BLOCKED] {gv.node}: {gv.problems}")
            return {
                "status": "blocked",
                "message": "안전 검증에서 문제가 발견되어 리포트를 제공할 수 없습니다. "
                           "전문가와 상담하시기를 권장드립니다.",
                "disclaimer": DISCLAIMER,
            }

        return {
            "status": "success",
            "message": "",
            "data": final_state.get(
                "final_report",
                {},
            ),
        }

    except Exception as e:
        return {
            "status": "fail",
            "message": str(e),
            "data": {},
        }


# ============================================================
# 서버 실행
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
