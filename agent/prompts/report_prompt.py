# -*- coding: utf-8 -*-
"""리포트 '설명 산문'만 생성하는 LangChain PromptTemplate.

불변식(TB-1): LLM은 숫자를 만들지 않는다. 아래 프롬프트는 이미 계산된 숫자를
**읽기전용 컨텍스트**로 주입하고, 모델에게 그 숫자를 바꾸지 말고 한국어 설명
산문만 쓰도록 강제한다. 산출물은 nodes/compliance 에서 숫자 부분집합 검증을
통과해야 리포트에 주입된다(위반 시 폐기 → 결정적 렌더).

참고 개념: LangChain PromptTemplate / {변수} 치환 (wikidocs 231233).
"""
from langchain_core.prompts import PromptTemplate

REPORT_PROSE_PROMPT = PromptTemplate.from_template(
    """너는 한국 성인 대상 영양제 추천 리포트의 '설명 산문'만 작성하는 도우미다.

[대상자(마스킹됨)]
{profile}

[엔진이 계산한 수치 — 읽기전용, 절대 변경 금지]
{numbers}

[작성 규칙]
- 위 수치를 근거로 대상자가 이해하기 쉬운 한국어 설명·요약·주의만 3~5문장으로 쓴다.
- 제공된 숫자만 인용한다. 새 숫자·새 수치·새 단위를 만들지 마라(제공 숫자 절대 변경 금지).
- 진단/처방 표현 금지. "참고용"임을 전제로 부드럽게 안내한다.
- 표·마크다운·HTML 태그 없이 순수 문장만 출력한다.
"""
)
