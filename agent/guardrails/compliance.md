# Compliance 가드레일 (최종 = 포맷 + PII)

## pre
- `aggregated_report`가 state에 존재.

## post — 포맷
- `final_report.html`는 비어있지 않은 str.
- `final_report.disclaimer`에 "의료법상" 정문구 포함.

## post — PII (항상 차단)
- 원본 name/birth_date(normalized_data)가 html에 평문으로 나타나지 않음.
- `final_report.user_profile.name`이 원본과 다름(마스킹됨).
- 주민등록번호(예: 000000-0000000)·전화번호(01x-xxxx-xxxx) 정규식 패턴 미노출.

PII 범위: 이름·생년월일·주민등록번호·전화번호. 입력 필드가 늘면 여기에 추가.

## 렌더 규칙 (숫자 안전 · TB-1)
- **숫자·표·게이지는 엔진 유래만.** 모든 수치는 `aggregated_report`(engine/MCP 결과)에서
  오며, Jinja2 결정적 렌더(`prompts/report_template.py`)가 그린다. LLM은 숫자를 만들지 않는다.
- **LLM은 설명 산문만.** `prompts/report_prompt.py`의 `PromptTemplate`이 이미 계산된 숫자를
  *읽기전용*으로 주입하고 한국어 설명만 요청한다(제공 숫자 절대 변경 금지).
- **기본 OFF.** `config.COMPLIANCE_LLM_PROSE`(기본 "0")일 때는 결정적 렌더만 — 네트워크 미사용,
  테스트 경로 결정적. "1"일 때만 산문 경로 시도.
- **숫자 부분집합 검증 + 결정적 폴백.** 산문의 숫자 토큰(`_numbers_in`)이 결정적 렌더의 숫자
  집합의 부분집합이 아니거나, LLM 실패/키 없음이면 산문을 폐기하고 결정적 렌더로 안전 강등한다
  (파이프라인 하드블록 아님).
- **마스킹은 노출 직전만.** `_mask_profile`은 이 노드에서만 수행하고 DB 원본은 건드리지 않는다.
- **데이터 간극.** case*.json 의 exam.groups/badges/bar/gauge 등 원천 없는 섹션은 조작하지 않고 생략한다.
