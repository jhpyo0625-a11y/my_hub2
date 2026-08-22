# MCP 서버 문제 진단 가이드

증상: agent 실행 시 `[MCP Warning] ... Client failed to connect: All connection attempts failed` → 매번 DB/deterministic fallback으로 강등.

아래를 **위에서부터** 하나씩 확인. 각 단계: 확인 명령 → 기대 → 실패 시 의미/조치.

---

## 0. 구성 요약 (무엇이 무엇과 통신하나)

- **서버**: `mcp/main.py`. `mcp.run(transport="http", host="0.0.0.0", port=8080)` → `http://localhost:8080/mcp/` 에서 표준 MCP(streamable-http) 제공. 9개 tool 등록.
- **클라이언트**: `agent/services/mcp_client.py`. `fastmcp.Client(MCP_SERVER_URL + "/mcp/")` → `client.call_tool(name, args)`.
- **접점**: `agent/.env`의 `MCP_SERVER_URL`(기본 `http://localhost:8080`) + `/mcp/`.

---

## 1. 서버가 떠 있나 (가장 흔한 원인)

"All connection attempts failed" = 8080에 **아무도 안 듣는 중**. 대개 서버 미기동.

```bash
cd mcp
uv sync
uv run python main.py        # http, 0.0.0.0:8080/mcp/
```
- **기대**: FastMCP 기동 로그 + 포트 8080 리슨. 이 터미널은 켜둔 채 agent를 **다른 터미널**에서 실행.
- 포트 확인 (별 터미널):
  ```bash
  # Windows
  netstat -ano | findstr :8080
  # 리슨 중이면 LISTENING 줄이 보임
  ```
- **실패 시**: 기동 로그에 에러 있으면 그걸로 감. 포트 점유 충돌이면 `MCP_PORT` 바꿔 실행(`MCP_PORT=8090 uv run python main.py`) + agent `.env`의 `MCP_SERVER_URL`도 맞추기.

---

## 2. 서버 로직 자체는 정상인가 (연결과 무관)

연결 문제와 tool 로직 문제를 분리하려면 selftest:

```bash
cd mcp
uv run python main.py --selftest
```
- **기대**: `selftest OK`. calculate_dynamic_ri/validate_ul/interactions/normalize 등 순수 로직 통과.
- **실패 시**: 연결이 아니라 tool 구현 문제. 해당 함수 고칠 것.

---

## 3. 엔드포인트/URL 일치

- `agent/.env`의 `MCP_SERVER_URL` 확인. 값이 `http://localhost:8080` (끝 슬래시/경로 없이). 클라이언트가 자동으로 `/mcp/`를 붙인다(`mcp_client.py`).
- 서버 transport가 **http**인지(위 1번, `--stdio` 아님). stdio로 띄우면 HTTP 클라이언트는 절대 못 붙는다.
- 빈 문자열 주의: `.env`에서 `MCP_SERVER_URL=` (빈값)이면 코드가 기본값으로 폴백하지만, 오타 URL이면 연결 실패.

---

## 4. 클라이언트 프로토콜 일치 (이미 교체됨 — 재확인)

과거 `mcp_client.py`는 커스텀 JSON-RPC(`POST /` 로 `tools/<name>`)라 FastMCP와 안 맞았음. 현재는 `fastmcp.Client`로 교체됨. 확인:
```bash
grep -n "fastmcp" agent/services/mcp_client.py
```
- **기대**: `from fastmcp import Client` + `client.call_tool(...)`.
- 안 보이면 옛 커스텀 클라이언트 → FastMCP와 프로토콜 불일치. SDK 클라이언트로 교체.

---

## 5. tool 이름 일치

agent Planner가 호출하는 4종: `calculate_dynamic_ri`, `validate_ul_guardrail`, `check_nutrient_interactions`, `search_products`. 서버 등록 목록과 대조:
```bash
grep -n "mcp.tool" mcp/main.py            # 등록 루프
grep -n "^def " mcp/main.py               # 함수명 = tool명
```
- **기대**: 위 4개가 서버에 존재(서버엔 9개 등록, 나머지는 미사용이라 무해).
- 이름 오타/누락 시 해당 tool만 실패.

---

## 6. MCP Inspector로 수동 프로브 (선택)

```bash
npx @modelcontextprotocol/inspector
```
- Inspector에서 `http://localhost:8080/mcp/`로 연결 → tool 목록 뜨고 수동 호출 가능하면 서버·엔드포인트 정상. 여기서 되면 문제는 agent 클라이언트 설정.

---

## 7. 서버는 붙는데 DB tool이 빈 결과일 때 (별개 이슈)

연결이 되어도 아래는 **데이터 계층 문제**라 따로 본다.

- **`search_products` 스키마 불일치 (실제 버그)**: `mcp/main.py`의 `search_products`는 `label_id, product_name, brand, form, nutrients(jsonb)` 컬럼을 쿼리한다. 그러나 실제 Neon `product_ingredients_master`는 **long-format**(`product_id, product_name, nutrient_code, amount_per_serving, unit`) — `label_id`/`nutrients` jsonb 없음. → 쿼리 실패 → `except`로 빈 `{"products": []}` 반환(조용히). MCP가 떠 있어도 제품이 안 나오면 이게 원인.
  - 조치: 서버 `search_products`를 long-format에 맞게 재작성(agent `services/db_helper.py:db_search_products`가 이미 올바른 버전 — 이식하면 됨).
- **`DATABASE_URL` 미설정**: 서버는 `mcp/`에서 `load_dotenv()` 한다. `mcp/.env`(또는 환경)에 `DATABASE_URL` 없으면 `_db_conn()`이 None → 제품/근거 tool 전부 빈 결과.
- **`search_evidence`는 항상 빈 결과**: `evidence_chunks` 테이블 + pgvector + `OPENAI_API_KEY`가 필요한데 현재 DB에 `evidence_chunks` 테이블이 없다. 근거 검색을 MCP로 쓰려면 테이블/임베딩 선구축 필요. (agent는 로컬 Chroma RAG를 쓰므로 이 tool에 의존하지 않음.)

---

## 8. 값 불일치 주의 (MCP up/down에 따라 숫자가 달라짐)

- 서버 `mcp/main.py`는 **자체 KDRI 표**를 가진다(예: calcium female **700**). agent DB fallback은 Neon `kdri_standards`를 읽는다(예: calcium female **650**). 두 소스가 다르면 **MCP 기동 여부에 따라 리포트 숫자가 바뀐다.**
- 조치: 단일 출처로 통일(권장: MCP도 Neon `kdri_standards`를 읽게 하거나, 반대로 통일). "모든 숫자는 국가기준에 추적 가능" 원칙상 두 표가 갈리면 안 됨.

---

## 9. MCP 없이도 동작함 (정상 설계)

MCP가 안 떠도 agent는 `MCP → Neon DB → deterministic` 3단 fallback으로 리포트를 만든다. 즉 "connect failed" 경고만으로 리포트가 깨지진 않는다. MCP를 **쓰려면** 위 1~6을, MCP 경유 제품/근거가 **비면** 7~8을 본다.

---

## 빠른 체크리스트

- [ ] `mcp`에서 `uv run python main.py` 기동, 8080 LISTENING
- [ ] `--selftest` 통과 (로직 정상)
- [ ] `agent/.env` `MCP_SERVER_URL=http://localhost:8080`
- [ ] `mcp_client.py`가 `fastmcp.Client` 사용
- [ ] tool 4종 이름 일치
- [ ] (제품 빈결과면) `search_products` long-format 재작성 + `mcp/.env` `DATABASE_URL`
- [ ] (숫자 검증) MCP KDRI 표 ↔ Neon `kdri_standards` 일치 여부
