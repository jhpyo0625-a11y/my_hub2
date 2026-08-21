# Precision Nutrition MCP Server

FastMCP 서버. `mcp_tools_specs.json`의 9개 tool을 제공한다.

## 실행

```bash
uv sync
uv run python main.py            # streamable-http, http://localhost:8080/mcp/
uv run python main.py --stdio    # stdio transport
uv run python main.py --selftest # 순수연산 tool 자체검증
```

## 프로토콜

표준 MCP (streamable-http). MCP SDK/`fastmcp.Client`로 접속.

> ⚠️ `agent/services/mcp_client.py`의 커스텀 JSON-RPC(`POST / tools/<name>`)는 표준
> MCP와 다르다. 이 서버를 쓰려면 클라이언트를 MCP SDK 기반으로 교체해야 한다.

## Tools

| tool | 데이터 출처 |
|------|-------------|
| calculate_dynamic_ri, validate_ul_guardrail | 내장 KDRI 참조표 (2025 성인 19+) |
| check_nutrient_interactions, normalize_medical_data | 내장 curated 규칙 |
| resolve_nutrient_codes, fill_missing_profile, compute_intake_coverage | 내장 참조표 |
| search_products, search_evidence | `DATABASE_URL`(+`OPENAI_API_KEY`) 있으면 Neon PostgreSQL, 없으면 빈 결과 |

## 환경변수 (선택)

- `MCP_PORT` (기본 8080)
- `DATABASE_URL` — Neon PostgreSQL. 제품/근거 검색용.
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `EMBED_MODEL` — 근거 검색 임베딩용.
