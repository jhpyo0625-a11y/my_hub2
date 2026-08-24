# task_new.md — Agent 리팩터링 & 에이전틱 강화 백로그

> task.md 후속. 원본은 보존하고 여기에 재정리.
> 원칙(변경 불가): **LLM은 숫자를 생성하지 않는다.** 엔진/툴이 계산, LLM은 자연어만
> (OCR·파싱·후속질문·설명 렌더의 4개 바운더리 콜사이트에서만). 모든 작업은 테스트
> 그린 유지 — TDD, 스펙이 진실.
>
> **테스트 실행(프레임워크 없음, pytest 아님)**:
> ```
> PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe test_pipeline.py
> PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe test_guardrails.py
> ```
> 둘 다 `ALL PASS` 나와야 함. MCP/DB 연결 실패 로그는 정상(fallback 경로).
>
> 순서대로 하나씩 구현. Phase 0 → 3. 각 Task는 독립 커밋 단위.

---

## 의존 그래프 (먼저 볼 것)

```
Phase 0 (빠른 수정, 저위험, 서로 독립)
  T0.1 MAX_RETRIES → config
  T0.2 State 스키마 키 선언
  T0.3 normalizer 마스킹 무판단 확인(테스트만)

Phase 1 (구조 정합)
  T1.1 PlanStep 공통 포맷 채택 (planner)  ─┐
  T1.2 PlanStep 채택 (executor 소비/산출)  ─┴─ T1.1 먼저
  T1.3 normalizer overwork 제거 (타깃선정 하류 이관)

Phase 2 (에이전틱 강화)
  T2.1 툴 arg 계약 → guardrail md 단일소스   (T1.1 이후)
  T2.2 planner 에이전틱 경계 가드레일 명문화
  T2.3 aggregator 최종 JSON 규격 소유
  T2.4 compliance 에이전틱 프롬프트 템플릿 렌더러  (T2.3 이후)

Phase 3 (외부 연동)
  T3.1 OCR 실연동 (Upstage) — 독립, 언제든
```

---

## Phase 0 — 빠른 수정

### T0.1 — MAX_RETRIES를 config/.env로 이관
**배경**: `nodes/reviewer.py:3`에 `MAX_RETRIES = 3` 하드코딩.
**함정(중요)**: 이 상수를 두 곳이 import 함.
`guardrails/checks.py:3`, `test_pipeline.py:8`. 순진하게 옮기면 두 import 깨짐.
**파일**: `config.py`, `.env`, `.env.example`, `nodes/reviewer.py`
**작업**:
1. `.env` + `.env.example`에 `MAX_RETRIES=3` 추가.
2. `config.py`에 `MAX_RETRIES = int(_get("MAX_RETRIES", "3"))` 노출.
3. `reviewer.py`: `from config import MAX_RETRIES`로 교체. **모듈 레벨에서 재노출**
   (`MAX_RETRIES = config.MAX_RETRIES` 또는 그대로 import 바인딩)해
   `checks.py`/`test_pipeline.py`의 `from nodes.reviewer import MAX_RETRIES` 유지.
**완료조건**: `.env`에서 값 바꾸면 재시도 한도 바뀜. `checks.py`·`test_pipeline.py`
import 무수정으로 통과.
**테스트**: 기존 `test_pipeline.py` 그린. `_get` 폴백("3") 확인 1줄 assert 추가.

### T0.2 — State 스키마에 누락 키 선언
**배경**: `raw_lab_results`를 normalizer가 쓰고(`normalizer.py:43`) planner·executor·
checks가 읽는데 `schemas/state.py State`에 **선언 없음**. total=False라 런타임은
통과하지만 스키마 드리프트. "state로 주고받기" 규율의 실질 항목.
**파일**: `schemas/state.py`
**작업**: `state[...]`에 쓰는 모든 키를 grep으로 감사 후 State에 추가. 최소:
`raw_lab_results: List[Dict[str, Any]]`. (감사: `grep -n 'state\["' nodes/*.py`)
**완료조건**: 코드가 쓰는 state 키 = TypedDict 선언 키. 누락 0.
**테스트**: 불필요(타입 선언). mypy 돌리면 보너스.

### T0.3 — normalizer 마스킹 무판단 확인 (이미 올바름)
**배경**: task.md line 7 우려는 **이미 충족**. 마스킹은 `compliance.py:_mask_profile`
에만 존재, normalizer는 `is_pii` 태깅만. 회귀 방지 테스트만 추가.
**파일**: `test_guardrails.py`(또는 신규 `test_normalizer.py`)
**작업**: normalizer 출력 `normalized_data["name"]`/`birth_date`가 원본 그대로(미마스킹)
이고 `is_pii` 태그 존재함을 assert.
**완료조건**: 테스트 그린. 향후 normalizer가 마스킹하면 실패.

---

## Phase 1 — 구조 정합

### T1.1 — PlanStep 공통 포맷 채택 (planner)
**배경**: `schemas/planner.py`의 `PlanStep`/`ExecutionPlan`이 LLM structured output
경로에서만 쓰이고, `_deterministic_plan`(planner.py:88-186)과 `_repair_args`는 raw
`dict` 조립. 포맷 이원화.
**파일**: `nodes/planner.py`, `schemas/planner.py`
**작업**:
1. `_deterministic_plan`이 `list[PlanStep]` 반환(또는 PlanStep로 검증 후 dump).
2. `_repair_args`도 PlanStep 필드로 접근/재구성.
3. state 저장 직전 한 곳에서만 `.model_dump()` (LangGraph state는 dict 유지).
   → LLM 경로/결정 경로 **동일 스키마** 통과.
**완료조건**: 두 계획 경로 모두 PlanStep 검증 통과. 잘못된 tool_name/필드는
Pydantic에서 조기 실패.
**테스트**: 결정적 계획이 9개 step, 각 `ToolName` Literal 준수 assert.

### T1.2 — executor에서 PlanStep 소비/산출 (T1.1 이후)
**배경**: executor는 계획을 raw dict로 소비, 결과도 임의 dict. 공통 포맷 미사용.
**파일**: `nodes/executor.py`, (필요시)`schemas/planner.py`에 `StepResult` 모델
**작업**:
1. `_batches`/`_run_step`/`_inject_dependencies`가 PlanStep 필드 기준으로 동작.
2. 결과 dict를 `StepResult`(step,task_name,tool_name,status,result,error_message)
   모델로 규격화 — reviewer/aggregator가 `.get()` 난사하는 현 구조를 스키마로 고정.
**완료조건**: executor 입출력이 선언 스키마 통과. reviewer/aggregator 소비 무변경 동작.
**테스트**: 병렬배치 1개+동시배치 섞인 계획으로 결과 형태 assert.
**ponytail**: `StepResult` 만들되 필드는 현재 쓰이는 것만. 미래 필드 금지.

### T1.3 — normalizer overwork 제거 (타깃 선정 하류 이관)
**배경**: `normalizer.py:84-91`이 OCR `status`(warning/deficient)를 **해석**해
target_nutrients 확장. 정규화 계층에 임상 판단 누수. normalizer는 규격 변환만.
**파일**: `nodes/normalizer.py`, `nodes/planner.py`
**작업**:
1. normalizer: `_DEFAULT_TARGETS` 코어 셋 + 원시 indicators 통과만. status 해석 제거.
   target_nutrients는 코어 셋만(또는 아예 planner로 이관).
2. planner: 코어 셋 + resolve된 코드 기준으로 타깃 확정. 이상지표 반영이 필요하면
   **툴 결과**(`normalize_medical_data`의 flag)로 판단 — LLM/정규화가 아니라 엔진이.
**완료조건**: normalizer가 status 문자열을 읽지 않음(grep으로 `deficient`/`warning`
없음 확인). 파이프라인 산출 동등.
**테스트**: 이상지표 OCR 입력 → 최종 타깃에 반영되되 그 결정이 normalizer 밖에서
일어남을 assert.
**주의**: 이상지표→타깃 연결을 어디로 옮길지는 T2.3(aggregator 규격)과 함께 확정.
지금은 코어 셋 유지가 안전한 하한.

---

## Phase 2 — 에이전틱 강화

### T2.1 — 툴 arg 계약을 guardrail md 단일소스로 (T1.1 이후)
**배경**: `_contract_args`(planner.py:8-47)와 `_deterministic_plan`, executor
`_inject_dependencies`에 툴별 arg가 **여러 곳 하드코딩**. 툴콜이 planner+executor
2개 사이트에서 일어남 → task.md 기준 md 파일 가드레일이 적합.
**파일**: `guardrails/planner.md`(기존), `mcp/mcp_tool_specs.json`(기존, 진실),
`nodes/planner.py`
**작업**:
1. 툴별 필요 arg 계약을 `mcp_tool_specs.json`(이미 존재) **단일 진실**로 삼음.
   `planner.md`는 사람이 읽는 요약, specs.json은 기계가 읽는 계약.
2. `_contract_args`가 arg **이름/구조**를 specs.json에서 파생하도록 리팩터(값은 state
   에서 결정적으로 채움). 새 툴 추가 시 Python 수정 없이 specs.json만.
**완료조건**: 툴 arg 스키마 변경이 specs.json 한 곳 수정으로 반영. planner 하드코딩
arg 목록 제거.
**테스트**: specs.json의 각 툴 required arg가 계획 step args에 존재함을 assert
(계약 준수 property 테스트).
**ponytail**: specs.json이 이미 계약을 담음 — 그걸 읽어라. 새 DSL 만들지 말 것.
값 주입 로직(state→args)은 Python에 남김(숫자 결정성 유지).

### T2.2 — planner 에이전틱 경계 명문화 (가드레일)
**배경**: "더 에이전틱" 요구와 **LLM 숫자 금지**(TB-1)가 충돌 지점. 현재 LLM은
tool 선택/순서/parallel_group만, arg 값은 결정적 — 이게 **의도된 안전 설계**.
느슨하게 풀면 LLM이 숫자 arg 생성 = 불변식 위반.
**파일**: `guardrails/planner.md`, `guardrails/checks.py`
**작업**:
1. `planner.md`에 하드 룰 명문화: LLM은 **tool_name·순서·parallel_group·재시도 전략·
   후속질문**만 결정. dose/RI/UL/수치 arg는 절대 생성 금지, state 파생값만.
2. `checks.py`에 post-planner 검증 추가: LLM 계획의 숫자 arg가 state 파생값과 불일치
   시 결정적 계약값으로 강제 덮어씀(이미 `_repair_args`가 함 — 이를 가드레일로 승격/명시).
**완료조건**: LLM이 임의 숫자를 arg에 넣어도 최종 계획엔 반영 안 됨(테스트로 증명).
**테스트**: 가짜 LLM 계획(숫자 오염 arg) 주입 → `_repair_args`/가드 후 계약값으로
정정됨 assert. **이게 에이전틱 자율과 안전의 경계선 증명.**

### T2.3 — aggregator가 최종 JSON 규격 소유
**배경**: 현재 aggregator→`aggregated_report`, compliance→`final_report`(html+마스킹)
로 규격 책임 분산. task.md 지적: 통합 agent가 **최종 산출 JSON 규격**을 만들어야.
**파일**: `schemas/models.py`, `nodes/aggregator.py`
**작업**:
1. `schemas/models.py`에 최종 리포트 canonical JSON 모델 정의(사용자 노출 전 구조).
   필드: profile, targets(RI), coverage, timing, products, guidelines(출처필수),
   ul_check, failed_items, lab_results. (지금 `AggregatedReport`를 이 규격으로 승격/정리.)
2. aggregator가 이 모델로 검증·산출. compliance는 **마스킹+렌더만**, 규격 생성 안 함.
**완료조건**: 최종 JSON 구조가 aggregator에서 확정. compliance는 소비자.
**테스트**: aggregator 출력이 canonical 모델 검증 통과, 무인용 guideline 배제
(`aggregator.py:59-72` 규칙) assert.

### T2.4 — compliance 에이전틱 프롬프트 템플릿 렌더러 (T2.3 이후) ★핵심
**배경**: `compliance.py:_render_html`(40-94) 거대 f-string. 요구: **에이전틱 프롬프트
템플릿**으로 설명형 리포트 생성. 참고 https://wikidocs.net/231233 (LangChain
PromptTemplate). 단, **LLM 숫자 생성 금지** — 하이브리드로 불변식 보존.
**설계(불변식 준수 하이브리드)**:
- **숫자/표는 Python이 렌더**(report dict → 결정적 HTML 표: RI·coverage·products).
- **설명 산문만 LLM**: PromptTemplate에 *이미 계산된 숫자를 컨텍스트로 주입*, LLM은
  그 숫자를 **바꾸지 말고** 한국어 설명·주의사항만 작성. 숫자를 새로 만들지 않음.
- **폴백**: API 키 없음/실패 → 현재 결정적 템플릿(문자열)로 렌더. 서비스 정직성 유지.
**파일**: `nodes/compliance.py`, 신규 `prompts/report_template.py`(또는 `.md`),
`guardrails/compliance.md`, `guardrails/checks.py`, `config.py`
**작업**:
1. `_render_html`을 (a)결정적 숫자 블록 + (b)LangChain `PromptTemplate`/
   `ChatPromptTemplate` 기반 설명 블록으로 분리. 템플릿 파일 외부화(`prompts/`).
2. LLM 입력: 마스킹된 profile + 계산 결과(숫자). 지시: "제공 숫자 불변, 설명만".
3. **가드레일 검증**(checks.py post-compliance): LLM 산출 텍스트의 숫자 토큰이 입력
   숫자 집합의 부분집합인지 확인 — 새 숫자 등장 시 블록(`on_violation="block"`
   이미 설정됨). 위반 시 결정적 폴백.
4. `compliance.md`에 렌더 규칙·면책·PII 원칙 명문화(하네스 가드레일).
**완료조건**: 리포트 설명이 LLM 산문으로 풍부해지되, 표시 숫자는 100% 엔진 유래.
키 없으면 결정적 폴백 동작.
**테스트**:
- 폴백 경로(키 없음) 렌더 성공 assert.
- **숫자 불변식**: 산출 HTML의 수치가 입력 report 수치 집합에 포함됨 assert
  (LLM이 숫자 조작 시 실패). ★가장 중요한 테스트.
**ponytail**: 표=Python, 산문=LLM. 전체를 LLM에 맡기지 말 것(숫자 위험). Jinja2
이미 설치됨 — 결정적 블록은 Jinja, LLM 블록은 PromptTemplate.

---

## Phase 3 — 외부 연동

### T3.1 — OCR 실연동 (Upstage Document AI)
**배경**: `services/ocr.py`가 하드코딩 가짜 검사수치 반환 stub(TODO만). 실제 OCR 없음.
**파일**: `services/ocr.py`, `config.py`, `.env(.example)`
**작업**:
1. Upstage Document AI 클라이언트 연동. `UPSTAGE_API_KEY` config 추가.
2. 파싱 결과 → 기존 `extracted_indicators` 스키마 매핑(단위 정규화 포함).
3. **status 필드는 OCR이 넣지 않음** — T1.3와 정합. OCR은 값/단위만, 임상 flag는
   `normalize_medical_data` 툴 소관.
4. 폴백: 키 없음/실패 → 현 stub(명시적 라벨) 유지, 개발 편의.
**완료조건**: 실이미지 → 실수치 추출. 키 없으면 stub.
**테스트**: 매핑 함수(파싱 원시 → indicators 스키마) 단위 테스트. 실 API 호출은
목/스킵.
**주의**: 실 API 키는 `.env`(이미 gitignore됨)만. 커밋 금지.

---

## 공통 체크리스트 (모든 Task)
- [ ] 테스트 그린: `test_pipeline.py` + `test_guardrails.py` 둘 다 `ALL PASS`
      (`PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe test_*.py`, pytest 아님)
- [ ] 새 로직엔 최소 1개 실행 가능한 검증 남김
- [ ] state 키 추가 시 `schemas/state.py`도 갱신 (T0.2 규율)
- [ ] 숫자는 엔진/툴만 — LLM 경로에 숫자 생성 없음 확인
- [ ] Windows 콘솔: 한글/µ 출력 시 `PYTHONIOENCODING=utf-8`

## 권장 구현 순서
T0.1 → T0.2 → T0.3 → T1.1 → T1.2 → T1.3 → T2.1 → T2.2 → T2.3 → T2.4 → T3.1
(Phase 0 세 개는 병렬 가능. T3.1은 독립이라 아무 때나.)
