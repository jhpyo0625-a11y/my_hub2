# API 데이터 규격서 (Input / Output)

> 지시사항 1 — Data 규격 확인
> 작성 기준: `main@b38c2fa` 의 실제 코드. 추정 없이 코드에서 확인한 것만 적었습니다.
> 팀원 백로그 `agent/task_new.md` 와의 대응은 §7 에 정리했습니다.
> 근거 파일: `schema/superset.json` · `frontend2/exam.py` · `agent/server.py` · `agent/nodes/*.py`

---

## 0. 이 문서가 하는 일

필드 **사전**은 이미 있습니다(`superset.json`, `matrix.md`). 이 문서는 그중
**API 경계에서 무엇을 어떤 타입·형태로 주고받을지**를 고르는 문서입니다.

새로 설계하는 부분은 §1 의 결정 4건뿐이고, 나머지는 현재 코드의 정리입니다.

---

## 1. 확정이 필요한 결정 — 4건

팀원 확인란입니다. O/X 만 표시해 주시면 나머지는 그대로 진행합니다.

| # | 결정 | 선택지 | 권고 | 이유 | 확인 |
|---|---|---|---|---|:--:|
| **D1** | `age` 타입 | 문자열 / **정수** | **정수** | 에이전트가 이미 `Form(int)` 로 선언. 화면은 `schema_bridge.to_number()` 로 변환 중 | ☐ |
| **D2** | `gender` 값 | `여성` / **`female`** | **`female`** | DB·MCP 가 영문 사용. 화면은 `SEX_TO_GENDER` 로 변환 중 | ☐ |
| **D3** | 중첩 구조 전달 | **JSON 문자열** / 평탄화 / JSON body | **JSON 문자열** | 검진표 이미지 때문에 multipart 를 못 버림. §2.2 참조 | ☐ |
| **D4** | Output 범위 | html 만 / **html + 구조화** | **둘 다** | 화면이 구조화 데이터로 그리려면 필요. §3.2 참조 | ☐ |

**D1·D2 는 이미 코드가 그렇게 동작합니다** — 확인만 하면 됩니다.
**D3·D4 가 실제 결정 사항입니다.**

---

## 2. Input 규격

### 2.1 `POST /api/v1/recommend`

`Content-Type: multipart/form-data`

| 필드 | 타입 | 필수 | 현재 | 예시 |
|---|---|:--:|:--:|---|
| `name` | string | | ✅ 있음 | `"김영희"` |
| `age` | integer | ✅ | ✅ 있음 | `62` |
| `gender` | `male` \| `female` | ✅ | ✅ 있음 | `"female"` |
| `weight_kg` | number | | ✅ 있음 | `58.0` |
| `birth_date` | string(YYYY-MM-DD) | | ✅ 있음 | 화면이 수집하지 않음 — 안 보냄 |
| `file` | binary | | ✅ 있음 | 검진표 이미지 |
| **`exam`** | **JSON 문자열** | | ❌ **추가 필요** | §2.3 |
| **`products`** | **JSON 문자열** | | ❌ **추가 필요** | §2.4 |
| **`meds`** | **JSON 문자열** | | ❌ **추가 필요** | §2.5 |
| **`chronic`** | **JSON 문자열** | | ❌ **추가 필요** | `["고혈압","당뇨"]` |

> **현재 6 / 목표 10.** 아래 4개가 없어서 화면 입력의 대부분이 전달되지 않습니다.
> 측정값은 `qa/out/coverage.md` 참조.

**호환성** — 지금 이 4개를 보내도 FastAPI 가 **조용히 무시**하므로 오류가 나지 않습니다
(실측: 필드를 넣은 응답과 뺀 응답의 html md5 가 동일). 따라서 **화면 쪽을 먼저 배포해도
안전하고**, 에이전트가 `Form()` 선언을 추가하는 순간 화면 수정 없이 동작합니다.

### 2.2 중첩 구조를 싣는 방법 (D3)

multipart 는 중첩 객체를 직접 표현하지 못합니다. 검진표 이미지 업로드 때문에
multipart 를 버릴 수 없으므로, 중첩 구조는 **JSON 문자열 한 칸**으로 싣습니다.

```
Content-Disposition: form-data; name="exam"

{"sbp":126,"dbp":78,"tg":210,"hdl":42,"tscore":-2.7}
```

받는 쪽:

```python
exam: Optional[str] = Form(None, description="검진 수치 JSON")
...
exam_data = json.loads(exam) if exam else {}
```

> 대안(평탄화 `exam.sbp=126`)은 배열을 표현하기 어렵고, JSON body 로 바꾸면
> 이미지 업로드를 별도 요청으로 쪼개야 합니다. 그래서 JSON 문자열을 권합니다.

### 2.3 `exam` — 검진 수치

**14개 그룹 · 입력 키 40개**입니다. 근거: `frontend2/exam.py` 의 `EXAM` 상수.

| 그룹 | 키 | 단위/형식 |
|---|---|---|
| 폐결핵·기타흉부질환 | `cxr` | select (정상/비활동성 폐결핵/그 외 소견) |
| 고혈압 | `sbp` `dbp` | mmHg |
| 비만 | `height` `weight` `waist` | cm / kg / cm |
| 빈혈 | `hb` | g/dL |
| 당뇨병 | `glu` | mg/dL |
| 이상지질혈증 | `tc` `hdl` `tg` `ldl` | mg/dL |
| 간장질환 | `ast` `alt` `ggt` | U/L |
| 신장질환 | `upro` `cr` `egfr` | select / mg/dL / mL/min |
| 골다공증 | `tscore` `bmd` | T / mg/㎤ |
| 노인 신체기능 | `leg` `balC` `balO` | 초 |
| 정신건강·인지 | `phq9` `phq9q9` `capeF` `capeD` `kdsq` | 점 / select |
| 청력 | `pta` `whisper` | dB / select |
| 만성폐쇄성폐질환 | `ratio` `fev1` `fvc` | % |
| 구강 | `caries` `suspect` `filled` `lost` `gingiva` `calculus` `plaque` | select / 점 |

> ⚠️ **`superset.json` 의 `ExamValues` 는 19개만 담고 있습니다.**
> 위 40개 중 21개(`bmd` `leg` `balC` `balO` `phq9` `phq9q9` `capeF` `capeD` `kdsq`
> `pta` `whisper` `ratio` `fev1` `fvc` `caries` `suspect` `filled` `lost` `gingiva`
> `calculus` `plaque`)가 빠져 있습니다. 추출 당시 표본(qa 케이스)이 19개만 써서
> 생긴 누락입니다. **규격은 `exam.py` 의 40개를 기준으로 합니다.**
>
> 🔴 **이 누락이 이미 전파됐습니다.** `agent/schemas/models.py:107` 의 `ExamValues`
> 모델도 같은 19개만 선언돼 있습니다(superset 을 근거로 만들어졌기 때문).
> `Base` 가 `extra="allow"` 라 값이 버려지지는 않지만, 타입 검증·자동완성·
> 하류 처리에서 21개가 빠집니다. **모델에 21개를 추가해야 합니다.**

값은 전부 **문자열로 와도 됩니다** — 화면이 문자열로 수집합니다. 받는 쪽에서
숫자로 바꿔 쓰시면 됩니다. 미입력 항목은 키 자체가 없습니다.

### 2.4 `products` — 복용 중인 영양제

```json
[
  {"name": "오메가3",
   "items": [{"name": "EPA+DHA", "amount": 1000, "unit": "mg"}]},
  {"name": "칼슘+비타민K",
   "items": [{"name": "칼슘",    "amount": 500, "unit": "mg"},
             {"name": "비타민K", "amount": 120, "unit": "mcg"}]}
]
```

| 경로 | 타입 | 설명 |
|---|---|---|
| `[].name` | string | 제품명 |
| `[].items[].name` | string | 성분명 (한글/영문 혼용) |
| `[].items[].amount` | number \| string | 함량. 빈 문자열 가능(함량 미기재) |
| `[].items[].unit` | string | `mg` `µg` `g` `IU` `mL` `억CFU` 중 하나 |

> `µ` 는 마이크로 기호(U+00B5)입니다. 그리스 문자 뮤(μ, U+03BC)와 다릅니다.

### 2.5 `meds` — 복용 중인 약

```json
[{"name": "와파린", "desc": "항응고제"}]
```

| 경로 | 타입 |
|---|---|
| `[].name` | string |
| `[].desc` | string (비어 있을 수 있음) |

### 2.6 `POST /api/v1/normalize` (검진표 판독)

현재 `recommend` 와 **같은 6필드**를 받습니다. 이미지 판독 전용이므로
`file` 이 핵심이고 나머지는 보조입니다. 추가 필드는 필요 없습니다.

---

## 3. Output 규격

### 3.1 응답 봉투

모든 응답이 이 모양입니다.

```json
{"status": "success", "message": "", "data": { ... }}
```

| `status` | 의미 | 화면 동작 |
|---|---|---|
| `success` | 정상 | `data` 로 리포트 표시 |
| `fail` | 서버 오류 | `message` 표시 후 재시도 안내 |
| `blocked` | 가드레일 차단 | 재시도해도 같으므로 재시도 버튼 숨김 |

### 3.2 `data` — 현재 vs 목표 (D4)

**현재** `agent/nodes/compliance.py:111` 이 담는 것 — **5개**:

| 필드 | 타입 | 설명 |
|---|---|---|
| `html` | string | 렌더 완료된 리포트 HTML |
| `user_profile` | object | **마스킹된** 프로필 (`김**트`) |
| `disclaimer` | string | 면책 문구 |
| `partial_failure` | boolean | 일부 툴 실패 여부 |
| `compliance_checked` | boolean | 마스킹 통과 여부 |

**목표** — 위 5개에 아래 9개를 **추가**합니다.

`agent/nodes/aggregator.py:74` 가 **이미 만들고 있는데** compliance 노드가 버리는 값들입니다.

| 필드 | 타입 | 만드는 곳 | 화면 용도 |
|---|---|---|---|
| `health_indicators` | object | OCR 지표 | 검진 판정 표 |
| `calculated_target` | object | `calculate_dynamic_ri` | 성분별 권장량 게이지 |
| `timing_guidance` | object | `check_nutrient_interactions` | 복용 시간 안내 |
| `products` | array | `search_products` | 추천 제품 카드 |
| `ul_check` | object | `validate_ul_guardrail` | 상한 초과 경고 |
| `coverage` | object | `compute_intake_coverage` | 충족률 막대 |
| `lab_results` | object | `normalize_medical_data` | 검진 수치 표 |
| `guidelines` | array | RAG | 참고 근거·인용 |
| `failed_items` | array | executor | 부분 실패 표시 |

**요청 내용은 "만들어 달라"가 아니라 "버리지 말아 달라"입니다.**

```python
# agent/nodes/compliance.py:111
state["final_report"] = {
    "html": html,
    "user_profile": masked_profile,
    "disclaimer": DISCLAIMER,
    "partial_failure": bool(failed),
    "compliance_checked": True,
    # ↓ 추가
    **{k: report.get(k) for k in (
        "health_indicators", "calculated_target", "timing_guidance",
        "products", "ul_check", "coverage", "lab_results",
        "guidelines", "failed_items")},
}
```

> ⚠️ **PII 주의** — `user_profile` 은 반드시 `_mask_profile()` 을 거친 것을 씁니다.
> 위 9개 필드에는 이름·생년월일이 들어가지 않으므로 그대로 실어도 됩니다.
> `FinalReport` 모델(`agent/schemas/models.py:238`)에도 필드를 추가해야 합니다.

### 3.3 화면 `Report` 규격 (참고)

화면이 구조화 데이터로 리포트를 그릴 때 쓰는 모양입니다. 에이전트가 이 모양으로
줄 필요는 없고, **화면 쪽 `schema_bridge.to_report_view()` 가 §3.2 를 이 모양으로
변환**합니다. 에이전트가 알아야 할 것은 §3.2 까지입니다.

| 필드 | 타입 | 내용 |
|---|---|---|
| `nutrients` | array | 성분 카드 (level: `met`/`low`/`near`/`over`) |
| `issues` | array | 상호작용·중복 점검 (kind, tone, text) |
| `exam` | object | `rows` `abnormal` `groups` `overall` `counts` `filled` |
| `recommend` | object | 추천 문단 |
| `summary` | object | 요약 문장 |
| `badges` `cols` `worst` `hasSupp` `mealOnly` `meta` `input` | — | 표시 보조 |

**검진 판정 코드** (`frontend2/exam.py` · 국가 건강검진 실시기준 [별표 4])

| 코드 | 의미 | 색 |
|---|---|---|
| `A` | 정상A | green |
| `B` | 경계 | yellow |
| `D` | 질환의심 | red |
| `N` | 미입력 | gray |

---

## 4. 변경 지점 요약

| # | 파일 | 위치 | 할 일 | 담당 |
|---|---|---|---|---|
| 1 | `agent/server.py` | `recommend_nutrition` (228행~) | `exam` `products` `meds` `chronic` **Form 선언 추가** | agent |
| 2 | `agent/server.py` | 270행 (recommend) · 182행 (normalize) | `"current_supplements": []` 하드코딩 → `products` 파싱 결과 | agent |
| 3 | `agent/nodes/normalizer.py` | 55행~ | 받은 값을 `normalized_data` 에 담기 | agent |
| 4 | `agent/nodes/compliance.py` | 111행 | `final_report` 에 구조화 9필드 추가 | agent |
| 5 | `agent/schemas/models.py` | `FinalReport` (238행) | 필드 추가 | agent |
| 6 | `frontend2/schema_bridge.py` | `to_recommend_form` (87행) | 전 필드 전송 | 프론트 |
| 7 | `frontend2/schema_bridge.py` | 신규 | `to_report_view()` — §3.2 → §3.3 매핑 | 프론트 |

---

## 5. 미해결 · 별도 확인

| 항목 | 상태 |
|---|---|
| `agent/services/ocr.py` | 49줄 전부 TODO. `image_bytes` 를 읽지 않고 고정 3지표 반환 |
| `/api/v1/normalize` 응답 | 판독 결과(`ocr_result` `target_nutrients`)가 응답에 없음 |
| `normalizer._DEFAULT_TARGETS` | 고정 4종. `_INDICATOR_TO_CODE` 매핑 3개뿐 |
| `superset.json ExamValues` | 19/40 — 21개 누락(§2.3). 재추출 필요 |

---

## 6. 부록 — 요청/응답 예시 한 벌

**요청**

```
POST /api/v1/recommend
Content-Type: multipart/form-data

name=김영희
age=62
gender=female
weight_kg=58
exam={"sbp":126,"dbp":78,"tg":210,"hdl":42,"tscore":-2.7}
products=[{"name":"오메가3","items":[{"name":"EPA+DHA","amount":1000,"unit":"mg"}]}]
meds=[{"name":"와파린","desc":"항응고제"}]
chronic=["고혈압"]
```

**응답**

```json
{
  "status": "success",
  "message": "",
  "data": {
    "html": "<section class=\"nutrition-report\">…</section>",
    "user_profile": {"name": "김**희", "age": 62, "gender": "female", "weight_kg": 58.0},
    "disclaimer": "본 추천 리포트는 AI 분석에 기반한 참고용 영양 정보이며…",
    "partial_failure": false,
    "compliance_checked": true,

    "health_indicators": {"Vitamin_D": {"value": 12.3, "status": "deficient"}},
    "calculated_target": {"custom_ri": {"vitamin_d": {"value": 10.0, "unit": "mcg"}}},
    "timing_guidance": {"time_separated_schedule": {"morning_AM": ["vitamin_d"], "evening_PM": []},
                        "cautions": ["와파린 복용 중 비타민K 섭취 주의"]},
    "products": [],
    "ul_check": {"is_safe": true, "ul_violations": []},
    "coverage": {"vitamin_d": {"pct": 30.0, "status": "deficient"}},
    "lab_results": {"results": [{"test_name": "tg", "value": 210, "unit": "mg/dL", "flag": "high"}]},
    "guidelines": [],
    "failed_items": []
  }
}
```

---

## 7. 팀원 백로그(`agent/task_new.md`)와의 대응

이 규격서를 쓴 뒤 `b38c2fa` 로 리팩터링 백로그가 올라왔습니다. **상당 부분이 이미
계획에 들어 있어**, 아래처럼 대응됩니다.

| 이 문서 | task_new.md | 상태 |
|---|---|---|
| **D4** (Output 구조화) | **T2.3** — aggregator 가 최종 JSON 규격 소유 | ✅ **사실상 확정** |
| §5 OCR 미구현 | **T3.1** — Upstage Document AI 연동, 키 없으면 stub | ✅ 계획됨 |
| §5 `_DEFAULT_TARGETS` 고정 | **T1.3** — 타깃 선정 하류 이관 | 🔄 일부 반영 |
| §2.1 Input 4필드 추가 | — | ❌ **백로그에 없음** |

### 7.1 D4 는 T2.3 으로 해결됩니다 — 필드명만 맞추면 됩니다

T2.3 이 정의하는 canonical JSON 필드와 §3.2 의 대응입니다.

| §3.2 (현 코드) | T2.3 (목표) |
|---|---|
| `user_profile` | `profile` |
| `calculated_target` | `targets` (RI) |
| `timing_guidance` | `timing` |
| `coverage` · `products` · `ul_check` · `lab_results` · `guidelines` · `failed_items` | 동일 |
| `health_indicators` | (T1.3 로 하류 이관 — 최종 JSON 포함 여부 확인 필요) |

**화면은 T2.3 의 이름을 따르겠습니다.** `schema_bridge.to_report_view()` 에서
흡수하므로 화면 코드에는 영향이 없습니다.

> ❓ **확인 필요**: `health_indicators` 를 최종 JSON 에 남길지. 검진 판정 표를
> 그리려면 필요합니다.

### 7.2 Input 확장은 백로그에 없습니다 ★

**T0~T3 어디에도 `recommend` 입력 필드 추가가 없습니다.** 출력(T2.3)과 OCR(T3.1)은
계획돼 있는데, **영양제·복용약·검진수치를 받는 통로(§2.1)** 는 빠져 있습니다.

이것이 없으면 T2.3 로 구조화 JSON 을 잘 만들어도 **담을 내용이 없습니다** —
지금 리포트가 누구에게나 같은 3개 영양소를 돌려주는 이유입니다.

**백로그에 추가를 요청드립니다.** 작업량은 §4 의 1·2·3 (Form 선언 4개 + 파싱)입니다.
