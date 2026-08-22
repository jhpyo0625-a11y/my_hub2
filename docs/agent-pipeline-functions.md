# 에이전트 파이프라인 함수 목록

`agent/` LangGraph 파이프라인의 노드별 함수. (`backup/` 폴더는 제외 — 구버전)

```
Normalizer → Planner → Executor → Reviewer → Aggregator → Compliance → END
```
각 노드는 `guard()` 하네스로 감싸짐(pre/post 체크). 위반 시 `GuardViolation` → `server.py` 차단.

---

## 1. Normalizer
입력 정규화 + OCR + PII 태깅 + target_nutrients 도출.

| 함수 | 위치 | 역할 |
|---|---|---|
| `input_normalization_node` | `nodes/normalizer.py:17` | 노드 본체. normalized_data 구성, PII 원본+is_pii 태깅, target_nutrients 도출 |
| `run_ocr_pipeline` | `services/ocr.py:4` | (사용) 이미지→구조화 지표. 현재 stub |
| `pre_normalizer` | `guardrails/checks.py:18` | 가드 pre: user_input 존재 |
| `post_normalizer` | `guardrails/checks.py:22` | 가드 post: age≥19, 성별 필수·기본값아님, age 누락아님, is_pii, target_nutrients |

## 2. Planner
ExecutionPlan 수립 (LLM 또는 결정적).

| 함수 | 위치 | 역할 |
|---|---|---|
| `planner_agent_node` | `nodes/planner.py:144` | 노드 본체. LLM 계획 또는 fallback 선택 |
| `_llm_plan` | `nodes/planner.py:103` | OpenAI structured output으로 계획 생성 (spec 프롬프트 주입) |
| `_deterministic_plan` | `nodes/planner.py:42` | 키/LLM 실패 시 결정적 4스텝 계획 |
| `_repair_args` | `nodes/planner.py:30` | LLM 계획의 args를 계약값으로 덮어씀 |
| `_contract_args` | `nodes/planner.py:8` | tool_name별 계약 args 구성 |
| `pre_planner` | `guardrails/checks.py:42` | 가드 pre: normalized_data+target_nutrients |
| `post_planner` | `guardrails/checks.py:51` | 가드 post: tool_name 4종, 필수 args, 의존순서 |

## 3. Executor
계획 실행 (병렬 + 3단 fallback).

| 함수 | 위치 | 역할 |
|---|---|---|
| `executor_node` | `nodes/executor.py:131` | 노드 본체. 배치별 실행·결과 수집 |
| `_batches` | `nodes/executor.py:115` | parallel_group으로 실행 배치 구성 |
| `_run_step` | `nodes/executor.py:89` | 단일 step 실행 (MCP→DB→stub fallback) |
| `_db_compute` | `nodes/executor.py:8` | MCP 실패 시 Neon DB 직접조회 |
| `_fallback` | `nodes/executor.py:35` | DB도 실패 시 결정적 대체값 |
| `_inject_dependencies` | `nodes/executor.py:74` | 교차-step 의존 주입(제품→proposed intake) |
| `call_mcp_tool` | `services/mcp_client.py:11` | (사용) MCP 툴 호출 |
| `db_calculate_ri` / `db_search_products` / `db_validate_ul` | `services/db_helper.py:49/75/112` | (사용) DB 기반 RI/제품/UL |
| `pre_executor` | `guardrails/checks.py:74` | 가드 pre: execution_plan 존재 |
| `post_executor` | `guardrails/checks.py:78` | 가드 post: 결과형태·status enum·custom_ri 누출 없음 |

## 4. Reviewer
셀프-커렉션 게이트 (재시도/부분실패).

| 함수 | 위치 | 역할 |
|---|---|---|
| `specialized_review_node` | `nodes/reviewer.py:6` | 노드 본체. 툴에러→executor, UL위반→planner, 3회 후 partial_failure |
| `MAX_RETRIES` (상수) | `nodes/reviewer.py:3` | 최대 재시도 3 |
| `pre_reviewer` | `guardrails/checks.py:96` | 가드 pre: execution_results 존재 |
| `post_reviewer` | `guardrails/checks.py:100` | 가드 post: review_status enum, retry_count≤MAX, failed_items 형식 |

## 5. Aggregator
결과 통합 + RAG 근거 보강.

| 함수 | 위치 | 역할 |
|---|---|---|
| `aggregator_node` | `nodes/aggregator.py:19` | 노드 본체. aggregated_report 조립 |
| `_rag_search` | `nodes/aggregator.py:4` | 확정 결과 근거용 Chroma RAG 검색 (lazy) |
| `RAGRetriever.search` | `rag_retriever.py:36` | (사용) 임베딩 검색 |
| `pre_aggregator` | `guardrails/checks.py:112` | 가드 pre: execution_results 존재 |
| `post_aggregator` | `guardrails/checks.py:116` | 가드 post: 필수키, 숫자 pass-through 동일, guidelines list[str] |

## 6. Compliance
PII 마스킹 + HTML 렌더 + disclaimer.

| 함수 | 위치 | 역할 |
|---|---|---|
| `legal_compliance_node` | `nodes/compliance.py:93` | 노드 본체. 마스킹·렌더·disclaimer·final_report |
| `_render_html` | `nodes/compliance.py:39` | 리포트→HTML |
| `_mask_profile` | `nodes/compliance.py:28` | is_pii 기반 프로필 마스킹(사본) |
| `_mask_name` | `nodes/compliance.py:11` | 이름 마스킹 (홍*동) |
| `_mask_birth` | `nodes/compliance.py:21` | 생년월일 마스킹 (19**-**-**) |
| `pre_compliance` | `guardrails/checks.py:139` | 가드 pre: aggregated_report 존재 |
| `post_compliance` | `guardrails/checks.py:143` | 가드 post(항상 block): html·disclaimer·PII 미노출 |

---

## 횡단 요소 (에이전트 아님)

**그래프** (`graph/workflow.py`)
- `build_workflow:35` — 노드 guard 래핑 + 엣지 구성
- `route_after_review:18` — Reviewer 조건부 라우팅 (executor/planner/aggregator)

**하네스** (`guardrails/harness.py`)
- `guard:31` — 노드 래퍼 (pre→노드→post)
- `GuardViolation:7` — 위반 예외
- `load_spec:14` — 노드 `.md` spec 로드 (프롬프트/참조)
- `flag:20` — 이탈 로그
- `_check:24` — flag+차단 판정 헬퍼

**설정/서비스**
- `config._get:13` — `.env` 값 로드
- `db_helper`: `get_db_connection:13`, `_gender_code:19`, `_fetch_units:23`, `_fetch_kdri_row:32` (+ 위 db_* 3개)
- `rag_retriever.RAGRetriever`: `__init__:18`, `search:36`, `count:69`

**API** (`server.py`)
- `recommend_nutrition:148` — `/api/v1/recommend`, graph 실행 + GuardViolation 차단
- `signup:57` / `login:108` — 인증 (별도 기능)
- `success_response:33` / `fail_response:41` — 공통 응답 형식

**테스트**
- `test_guardrails.py` — 가드레일 self-check (harness/노드6/wired_graph)
- `test_pipeline.py` — 파이프라인 회귀 (reviewer/executor/compliance)
