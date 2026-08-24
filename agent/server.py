import asyncio
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
from services import db_helper

from guardrails.harness import GuardViolation
from nodes.compliance import DISCLAIMER
from nodes.normalizer import input_normalization_node
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
    """회원 한 명을 users 테이블에 저장합니다.

    비밀번호는 bcrypt 해시로만 들어갑니다. 평문은 저장하지도, 로그에
    남기지도 않습니다.
    """
    user_id = db_helper.normalize_user_id(id)

    # 입력 검증은 DB 를 건드리지 않는 순수 함수로 빼 두었습니다(테스트 용이).
    problem = db_helper.validate_signup(user_id, pwd, name)
    if problem:
        return fail_response(problem)

    try:
        # psycopg 는 동기입니다. 그대로 부르면 DB 가 느릴 때 이벤트 루프가
        # 막혀 서버 전체가 멈춥니다. executor 와 같은 방식으로 감쌉니다.
        user = await asyncio.to_thread(
            db_helper.create_user, user_id, pwd, name
        )
    except db_helper.DuplicateUser:
        # 조회 후 삽입이 아니라 PK 제약이 잡아 줍니다 — 동시에 같은 아이디로
        # 두 번 들어와도 하나만 성공합니다.
        return fail_response("이미 존재하는 아이디입니다.")
    except Exception as e:
        # ★ str(e) 를 그대로 내보내지 않습니다. 예전에는 KeyError 가
        #   "'pwd'" 라는 문구로 사용자 화면까지 새어 나갔습니다.
        print(f"[signup] 실패: {type(e).__name__}: {e}")
        return fail_response("회원가입을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.")

    return success_response({"user": {"id": user["id"], "name": user["name"]}})


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
    """users 테이블에서 찾아 비밀번호 해시를 대조합니다."""
    try:
        user = await asyncio.to_thread(
            db_helper.authenticate, id, pwd
        )
    except Exception as e:
        print(f"[login] 실패: {type(e).__name__}: {e}")
        return fail_response("로그인을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.")

    if user is None:
        # ★ '없는 아이디' 와 '비밀번호 틀림' 을 구분해 알려 주지 않습니다.
        #   구분하면 어떤 아이디가 가입되어 있는지 확인하는 데 쓰입니다.
        return fail_response("아이디 또는 비밀번호가 올바르지 않습니다.")

    return success_response({"user": {"id": user["id"], "name": user["name"]}})


# ============================================================
# 검진표 정제 전용 API (신규)
# ============================================================

@app.post(
    "/api/v1/normalize",
    summary="검진표 이미지/데이터 정제 (Normalization)",
)
async def normalize_checkup(
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
    """검진표 파일 및 전달받은 인적사항을 input_normalization_node에 전달하여

    정제/표준화된 검진표 데이터(JSON)를 반환합니다.
    """
    try:
        image_bytes = None
        filename = None

        if file:
            image_bytes = await file.read()
            filename = file.filename

        # 1. 전달받은 정보를 user_input 딕셔너리로 패킹
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

        # 2. initial_state에 사용자 정보 및 이미지 데이터 저장
        initial_state: State = {
            "user_input": user_input,
            "retry_count": 0,
        }

        # 3. input_normalization_node 에이전트 실행
        # 노드의 동기/비동기 여부에 따라 처리
        if asyncio.iscoroutinefunction(input_normalization_node):
            normalized_state = await input_normalization_node(initial_state)
        else:
            normalized_state = await asyncio.to_thread(input_normalization_node, initial_state)

        # 4. 에이전트 처리 결과 추출
        normalized_result = normalized_state.get(
            "normalized_data", 
            normalized_state.get("user_input", {})
        )

        # 5. 공통 success_response 형식(JSON)으로 반환
        return success_response(data=normalized_result)

    # except GuardViolation as gv:
    #     print(f"[BLOCKED] {gv.node}: {gv.problems}")
    #     return {
    #         "status": "blocked",
    #         "message": "안전 검증에서 문제가 발견되어 리포트를 제공할 수 없습니다.",
    #         "disclaimer": DISCLAIMER,
    #     }

    except Exception as e:
        print(f"[recommend] 실패: {type(e).__name__}: {e}")
        return fail_response("검진표 분석 처리 중 오류가 발생했습니다.")


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
