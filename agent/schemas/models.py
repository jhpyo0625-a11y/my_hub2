# -*- coding: utf-8 -*-
"""파이프라인이 주고받는 페이로드의 통합 스키마.

    schema/matrix.md 의 병합 결과를 코드로 옮긴 것입니다.
    (원천 8곳 · 76 엔티티 · 360 필드를 훑어 10개 개념으로 병합)

설계 방침 -----------------------------------------------------------------
1. state.py(TypedDict)는 그대로 둡니다.
   LangGraph 상태를 Pydantic 으로 승격하면 nodes 안의 state["x"] 접근
   39곳을 전부 고쳐야 하고, 부분 업데이트 병합 의미도 달라집니다.
   여기서는 **상태의 껍데기가 아니라 그 안에 담기는 페이로드만** 검증합니다.
   노드는 한 줄씩만 추가하면 됩니다.

2. 한쪽 원천에만 있는 필드도 **버리지 않습니다.**
   matrix.md 기준 210필드 중 184개가 단 한 곳에만 존재했습니다.
   필드 수가 적은 쪽에도 고유 정보가 있습니다
   (체중 계수·상한 초과 수치·복용 시간대 등).

3. str 대신 Literal 을 씁니다. 오타가 런타임에 조용히 흐르지 않도록.
"""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ===========================================================================
# 열거형 — 지금까지 문자열로만 오가던 값들
# ===========================================================================
Gender = Literal["male", "female"]

# 프론트 화면이 쓰는 섭취 수준.
Level = Literal["over", "near", "low", "none", "unknown", "met"]

# MCP compute_intake_coverage 가 쓰는 충족 상태.
# ★ Level 과 합치지 않습니다 — 축이 다릅니다.
#   Level 은 '상한/권장 대비 어디쯤인가'(6단계),
#   CoverageStatus 는 '충족률이 부족/적정/과잉인가'(3단계)입니다.
#   합치면 near·none·unknown 이 갈 곳을 잃습니다.
CoverageStatus = Literal["deficient", "adequate", "excess"]

# 국가 건강검진 판정 (별표 4). '' 는 미입력.
JudgeCode = Literal["A", "B", "D", ""]

# 검사실 정상범위 기준 플래그. ★ JudgeCode 와 다른 축이라 둘 다 유지합니다.
LabFlag = Literal["low", "normal", "high"]

Tone = Literal["green", "orange", "red", "crit", "blue", "gray"]

ReviewStatus = Literal["pass", "reject_to_executor", "reject_to_planner"]

# 에이전트 API 응답 상태. blocked 는 가드레일 차단(재시도해도 같은 결과).
ResponseStatus = Literal["success", "fail", "blocked"]


class Base(BaseModel):
    """알 수 없는 필드가 와도 버리지 않고 보존합니다.

    원천이 8곳이라 아직 못 찾은 필드가 남아 있을 수 있습니다. 검증을
    도입하면서 오히려 데이터를 잃으면 본말전도입니다.
    """
    model_config = ConfigDict(extra="allow")


# ===========================================================================
# 입력
# ===========================================================================
class UserInput(Base):
    """server.py 의 recommend 가 조립해 graph 에 넘기는 것.

    ★ age·gender 를 필수로 둡니다.
      선언은 Optional 인데 normalizer 가 기본값(30·female)을 주입하고,
      그 직후 가드레일이 age_defaulted/gender_defaulted 를 보고 차단합니다.
      즉 **실질적으로는 필수**인데 선언만 선택이었습니다. 실측으로
      확인했습니다(4회 실행 중 누락 케이스 1회가 GuardViolation).
      여기서 필수로 못박아, 파이프라인 한참 뒤가 아니라 입구에서
      알아들을 수 있는 문구로 거절합니다.
    """
    age: int = Field(ge=0, le=120)
    gender: Gender
    name: str | None = None
    birth_date: str | None = None          # 'YYYY-MM-DD'
    weight_kg: float | None = Field(default=None, gt=0)
    current_supplements: list[dict[str, Any]] = Field(default_factory=list)
    # 검진표 이미지. 서버가 보관하지 않고 그대로 흘려보냅니다.
    image_bytes: bytes | None = None
    filename: str | None = None


class NormalizedData(Base):
    """normalizer 노드의 출력. compliance 의 마스킹이 이걸 봅니다."""
    units_normalized: bool = True
    name: str = "익명"
    birth_date: str | None = None
    age: int
    gender: Gender
    weight_kg: float = 60.0
    current_supplements: list[dict[str, Any]] = Field(default_factory=list)
    # 기본값으로 때운 항목. 가드레일이 이 둘을 보고 차단 여부를 정합니다.
    gender_defaulted: bool = False
    age_defaulted: bool = False
    # ★ compliance 마스킹이 참조하는 필드. 빠지면 실명이 그대로 노출됩니다.
    is_pii: dict[str, bool] = Field(default_factory=lambda: {"name": True, "birth_date": True})


# ===========================================================================
# 검진 수치 — 두 표현을 모두 유지합니다
# ===========================================================================
class ExamValues(Base):
    """화면이 쓰는 항목명 방식. 값은 전부 문자열입니다(빈 칸 허용)."""
    sbp: str = ""
    dbp: str = ""
    height: str = ""
    weight: str = ""
    waist: str = ""
    hb: str = ""
    glu: str = ""
    tc: str = ""
    hdl: str = ""
    tg: str = ""
    ldl: str = ""
    ast: str = ""
    alt: str = ""
    ggt: str = ""
    upro: str = ""
    cr: str = ""
    egfr: str = ""
    tscore: str = ""
    cxr: str = ""


class LabResult(Base):
    """MCP normalize_medical_data 가 쓰는 일반화 방식.

    ★ ExamValues 와 통합하지 않습니다. 항목명이 고정된 국가검진 서식과,
      임의 검사 이름을 받는 일반 표현은 용도가 다릅니다.
      항목명 ↔ test_name 매핑은 변환 계층이 담당합니다.
    """
    test_name: str
    value: float
    unit: str
    flag: LabFlag


# ===========================================================================
# 영양소
# ===========================================================================
class NutrientTarget(Base):
    """calculate_dynamic_ri 의 custom_ri 한 항목."""
    value: float
    unit: str = ""
    base: float | None = None            # 체중 보정 전 기준값
    factor_per_kg: float | None = None   # 체중 스케일 계수 (미구현 시 None)


class NutrientCoverage(Base):
    """compute_intake_coverage 의 coverage 한 항목."""
    pct: float
    status: CoverageStatus


# ===========================================================================
# 점검 결과
# ===========================================================================
class UlViolation(Base):
    """상한 초과 한 건. 화면 Issue 와 달리 **숫자 근거**를 갖고 있습니다."""
    nutrient: str
    total_intake: float
    ul_limit: float
    status: Literal["EXCEEDED"] = "EXCEEDED"


class TimeSeparatedSchedule(Base):
    """함께 먹으면 안 되는 성분을 아침·저녁으로 나눈 결과."""
    morning_AM: list[str] = Field(default_factory=list)
    evening_PM: list[str] = Field(default_factory=list)


class InteractionResult(Base):
    conflicts_found: bool = False
    time_separated_schedule: TimeSeparatedSchedule = Field(default_factory=TimeSeparatedSchedule)
    cautions: list[str] = Field(default_factory=list)


class UlCheckResult(Base):
    is_safe: bool = True
    ul_violations: list[UlViolation] = Field(default_factory=list)
    approved_recommendations: list[dict[str, Any]] = Field(default_factory=list)


# ===========================================================================
# 리포트
# ===========================================================================
class AggregatedReport(Base):
    """aggregator 노드의 출력."""
    title: str = "개인 맞춤형 정밀 영양 리포트"
    user_profile: dict[str, Any] = Field(default_factory=dict)
    health_indicators: dict[str, Any] = Field(default_factory=dict)
    calculated_target: dict[str, Any] = Field(default_factory=dict)
    timing_guidance: dict[str, Any] = Field(default_factory=dict)
    products: list[dict[str, Any]] = Field(default_factory=list)
    ul_check: dict[str, Any] = Field(default_factory=dict)
    failed_items: list[dict[str, Any]] = Field(default_factory=list)
    guidelines: list[Any] = Field(default_factory=list)
    # compute_intake_coverage 전체 결과 {"coverage":{...}}
    coverage: dict[str, Any] = Field(default_factory=dict)
    # normalize_medical_data 전체 결과 {"results":[...]}
    lab_results: dict[str, Any] = Field(default_factory=dict)


class FinalReport(Base):
    """compliance 노드의 출력. 화면이 그대로 그리는 html 이 여기 있습니다."""
    html: str
    user_profile: dict[str, Any] = Field(default_factory=dict)
    disclaimer: str = ""
    partial_failure: bool = False
    compliance_checked: bool = False


# ===========================================================================
# 인증
# ===========================================================================
class SessionUser(Base):
    """로그인·회원가입 응답.

    ★ id 와 email 을 둘 다 둡니다. 백엔드는 users.id, 화면은 email 로
      부르는데 같은 값입니다. 한쪽만 남기면 반대쪽 코드가 전부 깨집니다.
      변환 계층이 둘을 함께 채웁니다.
    """
    id: str = Field(max_length=50)   # prescription_histories.user_id 가 50자
    name: str = Field(max_length=100)
    email: str | None = None         # id 의 별칭


__all__ = [
    "Gender", "Level", "CoverageStatus", "JudgeCode", "LabFlag", "Tone",
    "ReviewStatus", "ResponseStatus",
    "UserInput", "NormalizedData", "ExamValues", "LabResult",
    "NutrientTarget", "NutrientCoverage",
    "UlViolation", "TimeSeparatedSchedule", "InteractionResult", "UlCheckResult",
    "AggregatedReport", "FinalReport", "SessionUser",
]
