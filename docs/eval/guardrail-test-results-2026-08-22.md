# 가드레일 하네스 테스트 결과

- **일자**: 2026-08-22
- **대상**: `agent/` 파이프라인의 에이전트별 하네스 가드레일
- **판정**: ✅ **전체 통과** (guardrail self-check + 파이프라인 회귀)
- **환경**: Python 3.11 (uv), Windows, Neon PostgreSQL 연결 가능, 로컬 MCP 서버(`localhost:8080`) 미기동 → DB/deterministic fallback 경로로 실행

---

## 1. 무엇을 검증했나

에이전트별 가드레일은 두 기능을 한다: (1) 노드별 `.md` spec을 참조하는 예비 체크, (2) 노드 출력이 established rule에서 이탈하면 flag/차단하는 안전망. 아래 두 스위트로 검증했다.

| 스위트 | 파일 | 목적 |
|---|---|---|
| 가드레일 self-check | `agent/test_guardrails.py` | 각 노드 가드의 pre/post 체크가 정상 출력은 통과시키고 위반 출력은 잡는지 + 하네스 차단 동작 + 그래프 배선 |
| 파이프라인 회귀 | `agent/test_pipeline.py` | 가드 배선 후에도 정상 파이프라인 흐름이 깨지지 않는지 |

---

## 2. 실행 방법

```bash
cd agent
PYTHONIOENCODING=utf-8 uv run python test_guardrails.py   # 가드레일 self-check
PYTHONIOENCODING=utf-8 uv run python test_pipeline.py      # 파이프라인 회귀
```

> Windows 콘솔은 cp949라 한글·µ 출력 시 `PYTHONIOENCODING=utf-8` 필수.

---

## 3. 결과 요약

| 스위트 | 종료코드 | 결과 |
|---|---|---|
| `test_guardrails.py` | 0 | ✅ ALL PASS |
| `test_pipeline.py` | 0 | ✅ ALL PASS |

### 가드레일 항목별 (test_guardrails.py)

| 검증 그룹 | 검사 내용 | 결과 |
|---|---|---|
| `harness` | `guard()` 래퍼 — post 이탈 시 `GuardViolation` 차단, `log` 모드 통과, pre 이탈 시 노드 실행 전 차단, `load_spec` 로드 | ✅ |
| `normalizer` | age ≥ 19, 성별 필수(기본값 금지), age 누락(`age_defaulted`) 차단, `is_pii` 태그, `target_nutrients` 비지 않음 | ✅ |
| `planner` | tool_name이 허용 4종, 툴별 필수 args, `validate_ul_guardrail`가 `search_products` 뒤(의존 순서) | ✅ |
| `executor` | 결과 형태·status enum, `custom_ri`에 0/None 숫자 누출 없음 | ✅ |
| `reviewer_guard` | `review_status` enum, `retry_count ≤ MAX_RETRIES`, `failed_items` 형식 | ✅ |
| `aggregator` | 필수키, 숫자 pass-through 동일성(조작·환각 유입 차단), guidelines list[str] | ✅ |
| `compliance` | html 비지 않음, disclaimer 정문구, PII(이름/생년월일 평문 미노출·마스킹 확인·주민번호/전화 정규식) | ✅ |
| `wired_graph` | 6노드 guard 래핑 상태로 정상 입력 시 `GuardViolation` 없이 완주, `final_report` 생성 | ✅ |

---

## 4. established rule 커버리지

| 룰 | 강제 지점 | 상태 |
|---|---|---|
| 성인 19세 이상만, 성별 필수(기본값 금지) | Normalizer 가드 | ✅ |
| LLM은 숫자를 만들지 않는다(출력 경계) | Executor 누출 금지 + Aggregator pass-through 동일성 | ✅ |
| 계획은 존재하는 툴만·의존 순서 준수 | Planner 가드 | ✅ |
| UL 재시도의 유한성 | Reviewer 가드(`retry_count ≤ MAX`) | ✅ |
| PII는 노출 시점에만 마스킹, disclaimer 필수 | Compliance 가드(항상 차단) | ✅ |
| 위반 시 fail-closed 차단 | `GuardViolation` → `server.py` 안전 거부 응답 | ✅ |

---

## 5. 참고: 로그의 MCP 연결 경고는 정상

테스트 중 `[MCP Warning] ... Client failed to connect` 로그가 보인다. 로컬 MCP 서버를 띄우지 않았기 때문이며, **의도된 fallback 동작**이다:

- 숫자 산출은 `MCP → Neon DB 직접조회 → deterministic` 3단 fallback으로 이어진다. 로그의 `-> DB 직접 조회 사용`이 실제 Neon에서 값을 가져온 것.
- 핵심: 가드가 배선된 상태에서도 정상 흐름이 차단 없이 완주(`wired_graph OK`, 회귀 `ALL PASS`)했다. 즉 **가드레일이 정상 리포트를 막지 않는다**는 것을 함께 확인했다.

---

## 부록 A — `test_guardrails.py` 원본 출력

```text
== GUARDRAILS ==
Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.
[GUARDRAIL] t 이탈 (spec=x.md): ['bad']
[GUARDRAIL] t 이탈 (spec=x.md): ['bad']
[GUARDRAIL] t 이탈 (spec=x.md): ['pre-bad']
  harness OK
  normalizer OK
  planner OK
  executor OK
  reviewer_guard OK
  aggregator OK
  compliance OK

[Node 1] Normalizer: 이미지 OCR 및 입력 데이터 정규화 처리 중...

[Node 2] Planner Agent: 오케스트레이터 LLM의 자율 작업 계획 수립...

[Node 3] Executor Node: MCP 서버 툴 호출 및 연산 실행 중...
  [MCP Tool Call] calculate_dynamic_ri 실행...
  [MCP Tool Call] check_nutrient_interactions 실행...
[MCP Warning] calculate_dynamic_ri 호출 중 예외 발생, fallback 연산 수행: Client failed to connect: All connection attempts failed
[MCP Warning] check_nutrient_interactions 호출 중 예외 발생, fallback 연산 수행: Client failed to connect: All connection attempts failed
    -> deterministic fallback 사용 (DB: no DB path for check_nutrient_interactions)
    -> DB 직접 조회 사용 (MCP: Client failed to connect: All connection attempts failed)
  [MCP Tool Call] search_products 실행...
  [MCP Tool Call] validate_ul_guardrail 실행...
[MCP Warning] validate_ul_guardrail 호출 중 예외 발생, fallback 연산 수행: Client failed to connect: All connection attempts failed
[MCP Warning] search_products 호출 중 예외 발생, fallback 연산 수행: Client failed to connect: All connection attempts failed
    -> DB 직접 조회 사용 (MCP: Client failed to connect: All connection attempts failed)
    -> DB 직접 조회 사용 (MCP: Client failed to connect: All connection attempts failed)

[Node 4] Reviewer Agent: 계산 수치 정밀도 및 Safety Guardrail 검수 중...
  -> ✅ 검수 통과: Aggregator로 이동.

[Node 5] Aggregator Agent: 결과 통합 및 RAG 지식 융합 중...
[RAG] Embedding model loading: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
Loading weights: 100%|██████████| 199/199 [00:00<00:00, 5628.19it/s]

[Node 6] Compliance Agent: PII 마스킹 및 HTML 렌더링 중...
  wired_graph OK
ALL PASS
GEXIT=0
```

## 부록 B — `test_pipeline.py` 원본 출력

```text
== PIPELINE ==

[Node 4] Reviewer Agent: 계산 수치 정밀도 및 Safety Guardrail 검수 중...

[Node 4] Reviewer Agent: 계산 수치 정밀도 및 Safety Guardrail 검수 중...

[Node 4] Reviewer Agent: 계산 수치 정밀도 및 Safety Guardrail 검수 중...

[Node 4] Reviewer Agent: 계산 수치 정밀도 및 Safety Guardrail 검수 중...
  -> ⛔ 재시도 3회 초과: 부분 실패 확정, 계속 진행.
  reviewer OK

[Node 3] Executor Node: MCP 서버 툴 호출 및 연산 실행 중...
  [MCP Tool Call] calculate_dynamic_ri 실행...
[MCP Warning] calculate_dynamic_ri 호출 중 예외 발생, fallback 연산 수행: Client failed to connect: All connection attempts failed
    -> DB 직접 조회 사용 (MCP: Client failed to connect: All connection attempts failed)
  [MCP Tool Call] search_products 실행...
  [MCP Tool Call] check_nutrient_interactions 실행...
[MCP Warning] search_products 호출 중 예외 발생, fallback 연산 수행: Client failed to connect: All connection attempts failed
[MCP Warning] check_nutrient_interactions 호출 중 예외 발생, fallback 연산 수행: Client failed to connect: All connection attempts failed
    -> deterministic fallback 사용 (DB: no DB path for check_nutrient_interactions)
    -> DB 직접 조회 사용 (MCP: Client failed to connect: All connection attempts failed)
  [MCP Tool Call] validate_ul_guardrail 실행...
[MCP Warning] validate_ul_guardrail 호출 중 예외 발생, fallback 연산 수행: Client failed to connect: All connection attempts failed
    -> DB 직접 조회 사용 (MCP: Client failed to connect: All connection attempts failed)
  executor OK

[Node 6] Compliance Agent: PII 마스킹 및 HTML 렌더링 중...
  compliance OK
ALL PASS
PEXIT=0
```
