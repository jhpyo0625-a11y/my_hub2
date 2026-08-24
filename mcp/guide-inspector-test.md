# MCP Inspector — 웹에서 툴 라이브 테스트

FastMCP 서버의 9개 tool을 브라우저 UI(MCP Inspector)에서 직접 호출해보는 가이드.

## 1. 서버 + 인스펙터 띄우기

두 개의 프로세스가 필요하다. 각각 별도 터미널에서 (현재 폴더 `mcp/`).

```bash
# (A) MCP 서버 — streamable-http, http://localhost:8080/mcp/
uv sync
uv run python main.py

# (B) 인스펙터 UI — http://localhost:6274
npx @modelcontextprotocol/inspector@0.14.0
```

> ⚠️ README의 `uv run fastmcp dev inspector main.py`는 인스펙터 `@latest`(2.3.0)를
> 끌어오는데, 현재 npm에서 `Invalid Version:` 버그로 실패한다. 위처럼 `@0.14.0`으로
> 핀 고정해서 직접 띄우면 된다. 0.14.0은 auth 토큰이 필요 없다.

## 2. 연결

브라우저에서 http://localhost:6274 열고:

1. **Transport Type** → `Streamable HTTP`
2. **URL** → `http://localhost:8080/mcp/`  (끝 슬래시 포함)
3. **Connect** → 상태가 초록 **Connected** 로 바뀜
4. **Tools** 탭 → **List Tools** → 9개 tool 표시

각 tool 클릭 → 입력 폼 채우고 → **Run Tool**. `object`/`array` 필드는 JSON으로 입력.

## 3. 툴별 샘플 입력

DB 불필요(내장 참조표)한 7개는 바로 된다. `search_products` / `search_evidence` 2개는
`DATABASE_URL`(+`OPENAI_API_KEY`) 있어야 결과가 나온다 — 없으면 빈 결과.

### resolve_nutrient_codes — 한글명 → 코드
```json
{ "names": ["비타민C", "마그네슘", "엽산"] }
```
기대: `vitamin_c` / `magnesium` / `folate`, confidence `synonym`.

### calculate_dynamic_ri — 개인 맞춤 권장섭취량
```json
{ "age": 30, "gender": "M", "weight_kg": 70,
  "target_nutrients": ["vitamin_c", "magnesium", "folate"] }
```

### validate_ul_guardrail — 상한(UL) 안전 검증
```json
{ "current_supps_intake":  { "vitamin_c": 500 },
  "diet_estimated_intake": { "vitamin_c": 100 },
  "proposed_supps_intake": { "vitamin_c": 3000 },
  "age": 30, "gender": "M", "weight_kg": 70 }
```
기대: `is_safe: false`, vitamin_c 3600 > UL 2000 → `EXCEEDED`.

### check_nutrient_interactions — 상호작용 점검
```json
{ "nutrient_list": ["calcium", "iron", "magnesium", "zinc"] }
```

### compute_intake_coverage — 섭취 대비 커버리지
```json
{ "intake":    { "vitamin_c": 200, "magnesium": 150 },
  "custom_ri": { "vitamin_c": 100, "magnesium": 350 } }
```

### fill_missing_profile — 누락 프로필 보정 (nullable 필드)
```json
{ "age": 30, "gender": "F", "weight_kg": null,
  "current_intake": null, "target_nutrients": ["iron", "folate"] }
```

### normalize_medical_data — 검사 결과 정규화
```json
{ "raw_lab_results": [
    { "name": "Vitamin D", "value": 18, "unit": "ng/mL" },
    { "name": "Ferritin",  "value": 12, "unit": "ng/mL" } ] }
```
> `raw_lab_results` 항목 스키마는 서버가 유연하게 받는다. 위 형태로 시작해서
> 결과의 정규화 필드를 보고 조정.

### search_products — 제품 검색 (DB 필요)
```json
{ "target_nutrients": ["vitamin_c", "magnesium"], "filters": null }
```

### search_evidence — 근거 검색 (DB + OpenAI 필요)
```json
{ "query": "마그네슘과 근육 경련", "nutrient_code": "magnesium", "k": 3 }
```

## 4. 결과 읽기

- **Tool Result: Success** + **Structured Content** — 구조화 JSON 출력
- **✓ Valid according to output schema** — 출력이 tool 스키마에 부합
- 우측 **History** 패널 — `initialize` → `tools/list` → `tools/call` 호출 이력

## 5. 문제 해결

| 증상 | 원인 / 조치 |
|------|-------------|
| 빨간 점, "Error Connecting to MCP Inspector Proxy" | 인스펙터 프록시(6277) 미기동. 인스펙터 재시작 (`--version` 같은 플래그 붙이지 말 것). |
| Connect 눌러도 Disconnected | 서버(8080) 안 떠 있음. `uv run python main.py` 확인. |
| URL 오타 | 반드시 `http://localhost:8080/mcp/` (끝 슬래시). |
| search_* 빈 결과 | `.env`에 `DATABASE_URL`(+`OPENAI_API_KEY`) 설정. |
| 순수연산 tool만 빠르게 검증 | `uv run python main.py --selftest` |
