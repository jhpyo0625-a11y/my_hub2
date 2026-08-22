# 에이전트별 하네스 가드레일 설계 (Lean)

- 상태: 승인됨 (2026-08-22)
- 대상: `agent/` 멀티에이전트 파이프라인 (LangGraph)
- 관련: `agent/graph/workflow.py`, `agent/nodes/*`, 기존 `agent/REVIEWER_GUARDRAILS.md`

## 1. 목적 (딱 둘)

각 에이전트(노드)에 얇은 가드레일을 붙여 established rule 이탈을 잡는다. 두 기능만 확실히 하고 끝낸다.

1. **참조 spec (예비 체크)**: 각 에이전트가 무엇을 입력받고 무엇을 출력해야 하는지를 노드별 `.md` 파일에 산문으로 쓴다. 이 `.md`는 (a) 사람이 읽는 계약 문서이자 (b) LLM 노드의 시스템 프롬프트에 주입되어 워크플로를 유도하는 규칙 소스다. 하네스의 **pre 단계**가 이 `.md`를 참조한다.
2. **안전망 (이탈 flag)**: 노드 실행 후 출력이 그 노드의 룰에서 벗어나면 하네스의 **post 단계**가 이탈을 flag(로그)하고, 기본적으로 파이프라인을 차단한다.

## 2. 원칙 / Non-goals

**원칙**
- 룰은 `.md`에 한 번 산문으로 작성한다. post 체크는 그 `.md`를 반영한 **얇은 손코딩 assert**다 — 결정적이고, 런타임 LLM 판정이 없다.
- 노드 코드는 순수하게 유지한다. 검증은 하네스 래퍼 한 곳에 모은다.
- 새 의존성 없음. pydantic(이미 설치)과 stdlib만 쓴다.

**Non-goals (이번 범위 밖 — 명시적으로 안 함)**
- 전역 리포트 숫자 재산출 오라클 / KDRI 재계산. (숫자 정확성은 생산 지점의 노드 체크로만 다룬다.)
- 가드레일발 복구 루프. 데이터 조건 재시도(UL 등)는 기존 Reviewer 노드가 계속 담당한다.
- 런타임 LLM 심판, `.md` 산문의 기계 해석(파서). `.md`는 텍스트로 읽어 프롬프트 주입/로그에만 쓴다.
- PII 원본 저장 정책·암호화. (별도 작업.)

## 3. 파일 레이아웃

```
agent/guardrails/
  __init__.py
  harness.py        # guard() 래퍼, GuardViolation, flag() 로깅
  checks.py         # 노드별 pre_/post_ 함수 (얇은 assert)
  normalizer.md     # 노드별 룰 산문 (참조 spec)
  planner.md
  executor.md
  reviewer.md       # 기존 REVIEWER_GUARDRAILS.md를 이리로 이동
  aggregator.md
  compliance.md
```

기존 루트의 `agent/REVIEWER_GUARDRAILS.md`는 `agent/guardrails/reviewer.md`로 이동한다.

## 4. 하네스 (harness.py)

```python
class GuardViolation(Exception):
    def __init__(self, node: str, problems: list[str]):
        self.node = node
        self.problems = problems
        super().__init__(f"{node}: {problems}")

def guard(fn, name, spec_md, pre=None, post=None, on_violation="block"):
    async def wrapped(state):
        if pre:
            pre(state)                         # 전제조건 검증. LLM 노드는 spec_md 주입도 여기서.
        state = await fn(state)
        problems = post(state) if post else []
        if problems:
            flag(name, spec_md, problems)      # 목적2: 이탈을 로그로 flag (spec_md 경로 인용)
            if on_violation == "block":
                raise GuardViolation(name, problems)
        return state
    return wrapped
```

- **pre = 예비 체크(목적1)**: 그 노드의 `.md`를 로드해 전제조건을 확인한다. LLM 노드(Planner)는 `.md` 룰 텍스트를 시스템 프롬프트에 주입해 워크플로를 유도한다. 전제조건 미충족도 이탈로 취급(raise).
- **post = 안전망(목적2)**: 이탈 문자열 리스트를 반환한다. 비어 있지 않으면 `flag()`가 `{node, spec_md, problems}`를 서버 로그에 남긴다.
- `flag()`는 서버 로그 전용 — 사용자에게 기술 사유를 노출하지 않는다.
- `on_violation`은 노드별 1줄 knob. 기본 `"block"`. `"log"`로 바꾸면 flag만 하고 통과. **Compliance의 PII 위반은 항상 `block`.**

## 5. workflow.py 배선

각 `add_node`를 `guard(...)`로 감싼다.

```python
workflow.add_node("planner_agent",
    guard(planner_agent_node, "planner", "guardrails/planner.md",
          pre=pre_planner, post=post_planner))
```

6개 노드(Normalizer, Planner, Executor, Reviewer, Aggregator, Compliance) 모두 래핑한다. `server.py`의 `graph.ainvoke` 호출을 `try/except GuardViolation`으로 감싸 차단 시 안전 거부 응답을 반환한다.

## 6. 노드별 룰 (최소)

| 노드 | pre | post — 이탈이면 flag |
|---|---|---|
| **Normalizer** | user_input 존재 | age는 int이고 **≥19**; gender ∈ {male, female}이고 **기본값으로 채워지지 않았음**(sex 필수); is_pii 태그 존재; target_nutrients는 비지 않은 list[str]. *(스코프 게이트 = 치명 → 차단·거부)* |
| **Planner** | normalized_data + target_nutrients 존재; planner.md 룰을 LLM 프롬프트에 주입 | execution_plan은 list; 모든 step.tool_name ∈ 4개 Literal; 툴별 필수 args 존재; **validate_ul_guardrail의 step번호 > search_products의 step번호**(의존 순서) |
| **Executor** | execution_plan 존재 | execution_results 비지 않음; 각 항목 status ∈ {success, error}; 성공 결과가 해당 툴 출력 형태(예: calculate_dynamic_ri → custom_ri dict); custom_ri 값에 **null/0 누출 없음** |
| **Reviewer** | execution_results 존재 | review_status ∈ enum; retry_count ≤ MAX_RETRIES; failed_items가 있으면 각 `{step, tool_name, status:"failed", reason}` 형식 |
| **Aggregator** | execution_results 존재 | aggregated_report 필수키 존재; **숫자 pass-through 동일** — calculated_target/ul_check가 execution_results의 값과 일치(조작·환각 유입 차단); guidelines는 list[str] |
| **Compliance** 〔최종 = 포맷 + PII〕 | aggregated_report 존재 | **포맷**: final_report.html 비지 않은 str; disclaimer 정문구 존재; 필수키 존재. **PII**: 원본 name/birth_date가 html에 평문으로 나타나지 않음 + 마스킹형 존재 + 주민등록번호/전화 정규식 패턴 미노출 |

## 7. 위반 시 동작 (block)

`GuardViolation` 발생 시 `server.py`가 반환:

```json
{
  "status": "blocked",
  "message": "안전 검증에서 문제가 발견되어 리포트를 제공할 수 없습니다. 전문가와 상담하시기를 권장드립니다.",
  "disclaimer": "본 추천 리포트는 AI 분석에 기반한 참고용 영양 정보이며, 의료법상 의사의 진단이나 처방을 대신할 수 없습니다."
}
```

기술적 problems 목록과 spec_md 경로는 서버 로그에만 남긴다(사용자 미노출).

## 8. PII 범위 (Compliance)

이름·생년월일·주민등록번호·전화번호. 앞의 둘은 `is_pii` 태그 기반 평문 미출현 검사, 뒤의 둘은 정규식 미노출 검사. 입력 필드가 늘면 `compliance.md`에 항목을 추가한다.

## 9. 테스트

`agent/test_guardrails.py` 하나. 프레임워크 없음. 각 노드에 대해:
- 정상 출력 state → 통과(problems 비어 있음).
- 고의로 손상시킨 출력 state → 해당 이탈 flag.

`guard()` 래퍼가 block 모드에서 `GuardViolation`을 raise하는지, log 모드에서 통과하는지도 각각 1케이스.

## 10. established rule 매핑 (근거)

- adults 19+, sex 필수·기본값 금지 → Normalizer.
- "LLM은 숫자를 만들지 않는다"의 출력 경계 강제 → Executor(누출 없음) + Aggregator(pass-through 동일).
- 계획 계약(존재하는 툴만, 의존 순서) → Planner.
- UL 재시도의 유한성 → Reviewer(retry_count ≤ MAX).
- PII는 노출 시점에만 마스킹, disclaimer 필수 → Compliance.
