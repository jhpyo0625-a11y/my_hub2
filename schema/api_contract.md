# API 데이터 규격서 (Input / Output)

> 지시사항 1 — Data 규격 확인
> 작성 기준: `main@99126a0` 의 실제 코드. 추정 없이 코드에서 확인한 것만 적었습니다.
> 근거: `frontend2/exam.py` · `agent/server.py` · `agent/nodes/*.py` · `agent/schemas/models.py`

**§6 에 Input·Output 전체 JSON 이 있습니다.** 빨리 보시려면 거기부터 보십시오.

---

## 0. 이 문서가 하는 일

필드 **사전**은 이미 있습니다(`superset.json`, `matrix.md`). 이 문서는 그중
**API 경계에서 무엇을 어떤 타입·형태로 주고받을지**를 확정하는 문서입니다.

---

## 1. 확정이 필요한 결정 — 4건

O/X 만 표시해 주시면 나머지는 그대로 진행합니다.

| # | 결정 | 권고 | 이유 | 확인 |
|---|---|---|---|:--:|
| **D1** | `age` 타입 = **정수** | 정수 | 에이전트가 이미 `Form(int)`. 화면은 `to_number()` 로 변환 중 | ☐ |
| **D2** | `gender` 값 = **`male`/`female`** | 영문 | DB·MCP 가 영문 사용. 화면은 `SEX_TO_GENDER` 로 변환 중 | ☐ |
| **D3** | 중첩 구조 = **JSON 문자열** | JSON 문자열 | 이미지 업로드 때문에 multipart 유지 필요. §2.2 | ☐ |
| **D4** | Output = **html + 구조화** | 둘 다 | 화면이 구조화로 그리려면 필요. §3.2 | ☐ |

**D1·D2 는 이미 코드가 그렇게 동작합니다** — 확인만 하면 됩니다.
**D4 는 `AggregatedReport` 가 이미 정본 계약으로 승격돼(§7.1) 사실상 확정입니다.**
남은 실질 결정은 **D3** 하나입니다.

---

## 2. Input 규격

### 2.1 `POST /api/v1/recommend` — 필드 10개

`Content-Type: multipart/form-data`

| 필드 | 타입 | 예시 | 현재 |
|---|---|---|:--:|
| `name` | string | `김영희` | ✅ |
| `age` | integer | `62` | ✅ |
| `gender` | `male`\|`female` | `female` | ✅ |
| `weight_kg` | number | `58.0` | ✅ |
| `birth_date` | `YYYY-MM-DD` | 화면이 수집 안 함 — 안 보냄 | ✅ |
| `file` | binary | 검진표 이미지 | ✅ |
| **`exam`** | JSON 문자열 | §2.3 · §6.1 | ❌ **추가** |
| **`products`** | JSON 문자열 | §2.4 | ❌ **추가** |
| **`meds`** | JSON 문자열 | §2.5 | ❌ **추가** |
| **`chronic`** | JSON 문자열 | `["고혈압","당뇨"]` | ❌ **추가** |

**전부 선택(Optional)입니다.** 사용자가 안 적은 항목은 키 자체가 오지 않습니다.

> **호환성** — 지금 이 4개를 보내도 FastAPI 가 **조용히 무시**하므로 오류가 나지
> 않습니다(실측: 넣은 응답과 뺀 응답의 html md5 동일 `17dcabceb7459ecb`).
> **화면 쪽을 먼저 배포해도 안전하고**, 에이전트가 `Form()` 을 추가하는 순간
> 화면 수정 없이 동작합니다.

### 2.2 `agent/server.py` 에 추가할 코드 (그대로 붙여 쓰십시오)

**① 파일 맨 위 import 에 `json` 추가** (이미 있으면 생략)

```python
import json
```

**② `recommend_nutrition` 시그니처에 4개 추가** — 228행 `weight_kg` 선언 **바로 뒤**

```python
    weight_kg: Optional[float] = Form(
        None,
        description="체중 (kg)",
    ),
    # ↓ 여기부터 추가 -------------------------------------------------------
    exam: Optional[str] = Form(
        None,
        description='검진 수치 JSON. 예: {"sbp":"126","dbp":"78","tg":"210"}',
    ),
    products: Optional[str] = Form(
        None,
        description='복용 중인 영양제 JSON. 예: [{"name":"오메가3","items":[...]}]',
    ),
    meds: Optional[str] = Form(
        None,
        description='복용 중인 약 JSON. 예: [{"name":"와파린","desc":"항응고제"}]',
    ),
    chronic: Optional[str] = Form(
        None,
        description='지병 JSON. 예: ["고혈압","당뇨"]',
    ),
    # ↑ 여기까지 -----------------------------------------------------------
):
```

**③ 본문에 파싱 헬퍼 추가** — `try:` 블록 안, `image_bytes = None` 앞

```python
        def _parse(raw, default):
            """JSON 문자열을 파싱한다. 깨져 있으면 기본값으로 넘어간다.

            한 칸이 잘못 왔다고 분석 전체를 막지 않는다 — 나머지 입력으로
            할 수 있는 만큼은 해 주는 편이 사용자에게 낫다.
            """
            if not raw:
                return default
            try:
                v = json.loads(raw)
            except (TypeError, ValueError):
                print(f"[recommend] JSON 파싱 실패, 무시: {str(raw)[:60]}")
                return default
            return v if isinstance(v, type(default)) else default

        exam_data = _parse(exam, {})
        products_data = _parse(products, [])
        meds_data = _parse(meds, [])
        chronic_data = _parse(chronic, [])
```

**④ `user_input` 에 담기** — 270행 `"current_supplements": []` 를 포함해 아래로 교체

```python
        user_input = {
            "name": name,
            "birth_date": birth_date,
            "age": age,
            "gender": gender,
            "weight_kg": weight_kg,
            "image_bytes": image_bytes,
            "filename": filename,
            # 하드코딩 [] 제거 — 실제 입력에서 채운다
            "current_supplements": [
                item.get("name", "")
                for p in products_data
                for item in (p.get("items") or [])
                if item.get("name")
            ],
            "products": products_data,   # 제품 단위 정보(중복 성분 판정에 필요)
            "meds": meds_data,
            "exam": exam_data,
            "chronic": chronic_data,
        }
```

> `current_supplements` 는 **성분 이름 목록**이고, `products` 는 **제품 단위**
> 구조입니다. 제품 간 성분 중복(같은 성분이 두 제품에 들어 있어 합산 시 상한
> 초과)을 잡으려면 제품 단위가 필요해서 둘 다 넘깁니다.

**⑤ `normalize_checkup` 에도 동일 적용** (135행~, 182행) — 검진표 판독 결과와
사용자가 직접 적은 수치를 함께 봐야 하므로 같은 필드가 필요합니다.

### 2.3 `exam` — 검진 수치 40항목 / 14그룹

근거: `frontend2/exam.py` 의 `EXAM` 상수. **모든 값은 문자열로 옵니다.**
미입력 항목은 키 자체가 없습니다.

#### 폐결핵·기타흉부질환
| 키 | 항목 | 형식 | 값 |
|---|---|---|---|
| `cxr` | 흉부방사선촬영 | 선택 | 정상 / 비활동성 폐결핵 / 그 외 소견 |

#### 고혈압
| 키 | 항목 | 단위 | 예시 |
|---|---|---|---|
| `sbp` | 혈압 — **수축기** | mmHg | `"126"` |
| `dbp` | 혈압 — **이완기** | mmHg | `"78"` |

#### 비만
| 키 | 항목 | 단위 | 예시 |
|---|---|---|---|
| `height` | 체질량지수(BMI) — **키** | cm | `"160"` |
| `weight` | 체질량지수(BMI) — **몸무게** | kg | `"58"` |
| `waist` | 허리둘레 | cm | `"82"` |

#### 빈혈 · 당뇨병
| 키 | 항목 | 단위 | 예시 |
|---|---|---|---|
| `hb` | 혈색소 | g/dL | `"11.4"` |
| `glu` | 공복혈당 | mg/dL | `"118"` |

#### 이상지질혈증
| 키 | 항목 | 단위 | 예시 |
|---|---|---|---|
| `tc` | 총콜레스테롤 | mg/dL | `"215"` |
| `hdl` | HDL 콜레스테롤 | mg/dL | `"42"` |
| `tg` | 중성지방 | mg/dL | `"210"` |
| `ldl` | LDL 콜레스테롤 | mg/dL | `"150"` |

#### 간장질환
| 키 | 항목 | 단위 | 예시 |
|---|---|---|---|
| `ast` | AST(SGOT) | U/L | `"28"` |
| `alt` | ALT(SGPT) | U/L | `"31"` |
| `ggt` | γ-GTP | U/L | `"45"` |

#### 신장질환
| 키 | 항목 | 형식 | 값 |
|---|---|---|---|
| `upro` | 요단백 | 선택 | 음성(-) / 약양성(±) / 양성(+1) 이상 |
| `cr` | 혈청크레아티닌 | mg/dL | `"0.8"` |
| `egfr` | 신사구체여과율(e-GFR) | mL/min | `"88"` |

#### 골다공증
| 키 | 항목 | 단위 | 예시 |
|---|---|---|---|
| `tscore` | 골밀도 T-score | T | `"-2.7"` |
| `bmd` | 골밀도(정량) | mg/㎤ | `"95"` |

#### 노인 신체기능
| 키 | 항목 | 단위 | 예시 |
|---|---|---|---|
| `leg` | 하지기능 | 초 | `"12"` |
| `balC` | 평형성 — **눈 감은 상태** | 초 | `"8"` |
| `balO` | 평형성 — **눈 뜬 상태** | 초 | `"25"` |

#### 정신건강·인지
| 키 | 항목 | 형식 | 값 |
|---|---|---|---|
| `phq9` | 우울증(PHQ-9) — **총점** | 점 | `"6"` |
| `phq9q9` | 우울증(PHQ-9) — **9번 문항** | 선택 | 0점 / 1점 이상 |
| `capeF` | 조기정신증(CAPE-15) — **빈도 총점** | 점 | `"18"` |
| `capeD` | 조기정신증(CAPE-15) — **고통 총점** | 점 | `"16"` |
| `kdsq` | 인지기능(KDSQ-C) | 점 | `"4"` |

#### 청력
| 키 | 항목 | 형식 | 값 |
|---|---|---|---|
| `pta` | 순음청력검사 | dB | `"35"` |
| `whisper` | 귓속말 검사 | 선택 | 양쪽 3개 이상 정확 / 한쪽이라도 3개 미만 |

#### 만성폐쇄성폐질환
| 키 | 항목 | 단위 | 예시 |
|---|---|---|---|
| `ratio` | 폐기능검사 — **FEV1/FVC** | % | `"72"` |
| `fev1` | 폐기능검사 — **FEV1** | % | `"81"` |
| `fvc` | 폐기능검사 — **FVC** | % | `"88"` |

#### 구강
| 키 | 항목 | 형식 | 값 |
|---|---|---|---|
| `caries` | 우식치아 | 선택 | 없음 / 있음 |
| `suspect` | 우식의심치아 | 선택 | 없음 / 있음 |
| `filled` | 수복치아 | 선택 | 없음 / 있음 |
| `lost` | 상실치아 | 선택 | 없음 / 있음 |
| `gingiva` | 치은염증 | 선택 | 없음 / 경증 / 중증 |
| `calculus` | 치석 | 선택 | 없음 / 경증 / 중증 |
| `plaque` | 치면세균막검사 | 점 | `"12"` |

> ⚠️ **`agent/schemas/models.py:107` 의 `ExamValues` 는 19개만 선언돼 있습니다.**
> 위 40개 중 21개(`bmd` `leg` `balC` `balO` `phq9` `phq9q9` `capeF` `capeD`
> `kdsq` `pta` `whisper` `ratio` `fev1` `fvc` `caries` `suspect` `filled`
> `lost` `gingiva` `calculus` `plaque`)가 빠져 있습니다.
>
> `superset.json` 을 근거로 만들어졌는데, 그 `superset.json` 이 런타임 표본
> (qa 케이스)에서 추출돼 표본에 없던 항목이 누락된 것입니다. **`Base` 가
> `extra="allow"` 라 값이 버려지지는 않지만, 타입 검증과 하류 처리에서
> 21개가 빠집니다. 모델에 추가해야 합니다.**

### 2.4 `products` — 복용 중인 영양제

| 경로 | 타입 | 설명 |
|---|---|---|
| `[].name` | string | 제품명 |
| `[].items[].name` | string | 성분명 (한글/영문 혼용) |
| `[].items[].amount` | number \| string | 함량. `""` 가능(라벨에 미기재) |
| `[].items[].unit` | string | `mg` `µg` `g` `IU` `mL` `억CFU` 중 하나 |

> `µ` 는 마이크로 기호(U+00B5). 그리스 문자 뮤(μ, U+03BC)와 다릅니다.

### 2.5 `meds` — 복용 중인 약

| 경로 | 타입 |
|---|---|
| `[].name` | string |
| `[].desc` | string (비어 있을 수 있음) |

### 2.6 `POST /api/v1/normalize` — 검진표 판독

`recommend` 와 **같은 10필드**를 받습니다(§2.2 ⑤). 이미지 판독 전용이므로
`file` 이 핵심입니다.

---

## 3. Output 규격

### 3.1 응답 봉투

```
{"status": "success", "message": "", "data": { ... }}   ← data 내용은 §3.2
```

| `status` | 의미 | 화면 동작 |
|---|---|---|
| `success` | 정상 | `data` 로 리포트 표시 |
| `fail` | 서버 오류 | `message` 표시 + 재시도 버튼 |
| `blocked` | 가드레일 차단 | 재시도해도 같으므로 **재시도 버튼 숨김** |

### 3.2 `data` — 현재 5개 → 목표 14개

**현재** (`agent/nodes/compliance.py:111`):

| 필드 | 타입 | 설명 |
|---|---|---|
| `html` | string | 렌더 완료된 리포트 HTML |
| `user_profile` | object | **마스킹된** 프로필 (`김**희`) |
| `disclaimer` | string | 면책 문구 |
| `partial_failure` | boolean | 일부 툴 실패 여부 |
| `compliance_checked` | boolean | 마스킹 통과 여부 |

**추가할 9개** — `aggregator` 가 **이미 만들고 있는데** compliance 가 버리는 값들:

| 필드 | 타입 | 내용 | 화면 용도 |
|---|---|---|---|
| `health_indicators` | object | `{지표명: {status, value}}` | 검진 판정 표 |
| `calculated_target` | object | `{custom_ri: {코드: NutrientTarget}}` | 권장량 게이지 |
| `timing_guidance` | object | `InteractionResult` | 복용 시간 안내 |
| `products` | array | 추천 제품 | 제품 카드 |
| `ul_check` | object | `UlCheckResult` | 상한 초과 경고 |
| `coverage` | object | `{coverage: {코드: NutrientCoverage}}` | 충족률 막대 |
| `lab_results` | object | `{results: [LabResult]}` | 검진 수치 표 |
| `guidelines` | array | `[{text, source}]` | 참고 근거 |
| `failed_items` | array | 실패한 툴 | 부분 실패 표시 |

> **요청 내용은 "만들어 달라"가 아니라 "버리지 말아 달라"입니다.**

### 3.3 `agent/nodes/compliance.py` 에 추가할 코드

111행 `state["final_report"] = {` 블록을 아래로 교체:

```python
    # aggregator 가 만든 구조화 필드를 그대로 실어 보낸다.
    # 화면이 html 덩어리 대신 이 값들로 리포트를 그린다.
    # user_profile 만은 반드시 마스킹된 것을 쓴다(원본에 이름이 들어 있다).
    PASS_THROUGH = (
        "health_indicators", "calculated_target", "timing_guidance",
        "products", "ul_check", "coverage", "lab_results",
        "guidelines", "failed_items",
    )
    state["final_report"] = {
        "html": html,
        "user_profile": masked_profile,
        "disclaimer": DISCLAIMER,
        "partial_failure": bool(failed),
        "compliance_checked": True,
        **{k: report.get(k) for k in PASS_THROUGH},
    }
```

`agent/schemas/models.py:238` 의 `FinalReport` 에도 같은 9개 필드를 추가해야
합니다(`AggregatedReport` 의 선언을 그대로 복사하면 됩니다).

> ⚠️ **PII** — 위 9개에는 이름·생년월일이 들어가지 않으므로 그대로 실어도
> 됩니다. `user_profile` 만 `_mask_profile()` 을 거친 값을 씁니다.

### 3.4 화면 `Report` 규격 (참고 — 에이전트는 몰라도 됩니다)

화면 쪽 `schema_bridge.to_report_view()` 가 §3.2 를 아래 모양으로 변환합니다.

| 필드 | 내용 |
|---|---|
| `nutrients` | 성분 카드. `level`: `met`/`low`/`near`/`over` |
| `issues` | 상호작용·중복 점검. `kind` `tone` `text` |
| `exam` | `rows` `abnormal` `groups` `overall` `counts` `filled` |
| `recommend` `summary` `badges` `cols` `worst` `hasSupp` `mealOnly` `meta` `input` | 표시 보조 |

**검진 판정 코드** (국가 건강검진 실시기준 [별표 4])

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
| 1 | `agent/server.py` | 228행~ | `recommend` 에 Form 4개 추가 (§2.2 ②③④) | agent |
| 2 | `agent/server.py` | 135행~ | `normalize` 에 동일 적용 (§2.2 ⑤) | agent |
| 3 | `agent/nodes/normalizer.py` | 55행~ | 받은 값을 `normalized_data` 에 담기 | agent |
| 4 | `agent/nodes/compliance.py` | 111행 | `final_report` 에 9필드 추가 (§3.3) | agent |
| 5 | `agent/schemas/models.py` | 107행 | `ExamValues` 에 21필드 추가 (§2.3) | agent |
| 6 | `agent/schemas/models.py` | 238행 | `FinalReport` 에 9필드 추가 | agent |
| 7 | `frontend2/schema_bridge.py` | 87행 | `to_recommend_form` 확장 | 프론트 |
| 8 | `frontend2/schema_bridge.py` | 신규 | `to_report_view()` — §3.2 → §3.4 | 프론트 |

---

## 5. 미해결 · 별도 확인

| 항목 | 상태 |
|---|---|
| `agent/services/ocr.py` | 49줄 전부 TODO. `image_bytes` 를 읽지 않고 고정 3지표 반환 → **T3.1** 로 계획됨 |
| `/api/v1/normalize` 응답 | 판독 결과(`ocr_result` `target_nutrients`)가 응답에 없음 |
| `normalizer._DEFAULT_TARGETS` | 고정 4종. `_INDICATOR_TO_CODE` 매핑 3개뿐 → **T1.3** 진행 중 |
| `superset.json ExamValues` | 19/40. `extract.py` 가 `exam.py` 의 `EXAM` 을 읽도록 수정 필요 |

---

## 6. 전체 JSON

### 6.1 Input — 화면이 들고 있는 전체 모양

`frontend2` 의 `AnalysisInput`. 이것이 §6.2 의 multipart 로 변환됩니다.

```json
{
  "name": "김영희",
  "age": "62",
  "sex": "여성",
  "date": "2026-03-10",
  "countMeal": true,
  "chronic": ["고혈압"],

  "exam": {
    "cxr": "정상",
    "sbp": "126", "dbp": "78",
    "height": "160", "weight": "58", "waist": "82",
    "hb": "11.4",
    "glu": "118",
    "tc": "215", "hdl": "42", "tg": "210", "ldl": "150",
    "ast": "28", "alt": "31", "ggt": "45",
    "upro": "음성(-)", "cr": "0.8", "egfr": "88",
    "tscore": "-2.7", "bmd": "95",
    "leg": "12", "balC": "8", "balO": "25",
    "phq9": "6", "phq9q9": "0점", "capeF": "18", "capeD": "16", "kdsq": "4",
    "pta": "35", "whisper": "양쪽 3개 이상 정확",
    "ratio": "72", "fev1": "81", "fvc": "88",
    "caries": "없음", "suspect": "없음", "filled": "있음", "lost": "없음",
    "gingiva": "경증", "calculus": "경증", "plaque": "12"
  },

  "products": [
    {"name": "오메가3",
     "items": [{"name": "EPA+DHA", "amount": 1000, "unit": "mg"}]},
    {"name": "칼슘+비타민K",
     "items": [{"name": "칼슘",     "amount": 500,  "unit": "mg"},
               {"name": "비타민K",  "amount": 120,  "unit": "µg"},
               {"name": "비타민 D", "amount": 1000, "unit": "IU"}]}
  ],

  "meds": [
    {"name": "와파린", "desc": "항응고제"}
  ]
}
```

> `sex`(한글) → `gender`(영문), `age`(문자열) → 정수 변환은 화면 쪽
> `schema_bridge` 가 담당합니다. **에이전트는 §6.2 형태로 받습니다.**

### 6.2 Input — 실제로 전송되는 multipart

```
POST /api/v1/recommend HTTP/1.1
Content-Type: multipart/form-data; boundary=----X

------X
Content-Disposition: form-data; name="name"

김영희
------X
Content-Disposition: form-data; name="age"

62
------X
Content-Disposition: form-data; name="gender"

female
------X
Content-Disposition: form-data; name="weight_kg"

58.0
------X
Content-Disposition: form-data; name="exam"

{"cxr":"정상","sbp":"126","dbp":"78","height":"160","weight":"58","waist":"82","hb":"11.4","glu":"118","tc":"215","hdl":"42","tg":"210","ldl":"150","ast":"28","alt":"31","ggt":"45","upro":"음성(-)","cr":"0.8","egfr":"88","tscore":"-2.7","bmd":"95","leg":"12","balC":"8","balO":"25","phq9":"6","phq9q9":"0점","capeF":"18","capeD":"16","kdsq":"4","pta":"35","whisper":"양쪽 3개 이상 정확","ratio":"72","fev1":"81","fvc":"88","caries":"없음","suspect":"없음","filled":"있음","lost":"없음","gingiva":"경증","calculus":"경증","plaque":"12"}
------X
Content-Disposition: form-data; name="products"

[{"name":"오메가3","items":[{"name":"EPA+DHA","amount":1000,"unit":"mg"}]},{"name":"칼슘+비타민K","items":[{"name":"칼슘","amount":500,"unit":"mg"},{"name":"비타민K","amount":120,"unit":"µg"},{"name":"비타민 D","amount":1000,"unit":"IU"}]}]
------X
Content-Disposition: form-data; name="meds"

[{"name":"와파린","desc":"항응고제"}]
------X
Content-Disposition: form-data; name="chronic"

["고혈압"]
------X
Content-Disposition: form-data; name="file"; filename="exam.jpg"
Content-Type: image/jpeg

<바이너리>
------X--
```

### 6.3 Output — 전체 (D4 적용 후)

```json
{
  "status": "success",
  "message": "",
  "data": {
    "html": "<section class=\"nutrition-report\">…</section>",

    "user_profile": {
      "units_normalized": true,
      "name": "김**희",
      "birth_date": null,
      "age": 62,
      "gender": "female",
      "weight_kg": 58.0,
      "current_supplements": ["EPA+DHA", "칼슘", "비타민K", "비타민 D"],
      "gender_defaulted": false,
      "age_defaulted": false,
      "is_pii": {"name": true, "birth_date": true}
    },

    "health_indicators": {
      "Vitamin_D":    {"value": 12.3, "unit": "ng/mL", "status": "deficient"},
      "Calcium":      {"value": 9.5,  "unit": "mg/dL", "status": "normal"},
      "Triglyceride": {"value": 210,  "unit": "mg/dL", "status": "warning"}
    },

    "calculated_target": {
      "custom_ri": {
        "vitamin_d": {"value": 10.0,   "unit": "mcg", "base": 10.0,   "factor_per_kg": null},
        "calcium":   {"value": 800.0,  "unit": "mg",  "base": 800.0,  "factor_per_kg": null},
        "magnesium": {"value": 280.0,  "unit": "mg",  "base": 280.0,  "factor_per_kg": null},
        "epa_dha":   {"value": 1000.0, "unit": "mg",  "base": 1000.0, "factor_per_kg": null}
      }
    },

    "timing_guidance": {
      "conflicts_found": true,
      "time_separated_schedule": {
        "morning_AM": ["vitamin_d", "calcium"],
        "evening_PM": ["magnesium", "epa_dha"]
      },
      "cautions": [
        "칼슘과 철분은 2시간 시차 복용 권장",
        "와파린 복용 중 비타민K 섭취량을 일정하게 유지하세요"
      ]
    },

    "coverage": {
      "coverage": {
        "vitamin_d": {"pct": 30.0,  "status": "deficient"},
        "calcium":   {"pct": 62.5,  "status": "deficient"},
        "magnesium": {"pct": 0.0,   "status": "deficient"},
        "epa_dha":   {"pct": 100.0, "status": "sufficient"}
      }
    },

    "ul_check": {
      "is_safe": false,
      "ul_violations": [
        {"nutrient": "vitamin_d",
         "total_intake": 4200.0,
         "ul_limit": 4000.0,
         "status": "EXCEEDED"}
      ],
      "approved_recommendations": [
        {"nutrient_code": "calcium", "amount": 300, "unit": "mg"}
      ]
    },

    "lab_results": {
      "results": [
        {"test_name": "tg",     "value": 210.0, "unit": "mg/dL", "flag": "high"},
        {"test_name": "hdl",    "value": 42.0,  "unit": "mg/dL", "flag": "low"},
        {"test_name": "tscore", "value": -2.7,  "unit": "T",     "flag": "low"},
        {"test_name": "glu",    "value": 118.0, "unit": "mg/dL", "flag": "high"}
      ]
    },

    "products": [
      {"label_id": 10231,
       "product_name": "칼슘 마그네슘 비타민D",
       "brand": "○○헬스",
       "form": "정제",
       "nutrients": {"calcium": 300, "magnesium": 150, "vitamin_d": 10}}
    ],

    "guidelines": [
      {"text": "골밀도 T-score −2.5 이하는 골다공증 범위로, 칼슘·비타민D 섭취를 함께 확인합니다.",
       "source": "국가 건강검진 실시기준 [별표 4] p.12"},
      {"text": "와파린 복용자는 비타민K 섭취량의 급격한 변동을 피해야 합니다.",
       "source": "약물-영양소 상호작용 지침 row 44"}
    ],

    "failed_items": [],

    "disclaimer": "본 추천 리포트는 AI 분석에 기반한 참고용 영양 정보이며, 의료법상 의사의 진단이나 처방을 대신할 수 없습니다.",
    "partial_failure": false,
    "compliance_checked": true
  }
}
```

### 6.4 Output — 차단(`blocked`)

가드레일에 걸리면 `data` 가 없습니다.

```json
{
  "status": "blocked",
  "message": "안전 검증에서 문제가 발견되어 리포트를 제공할 수 없습니다. 전문가와 상담하시기를 권장드립니다.",
  "disclaimer": "본 추천 리포트는 AI 분석에 기반한 참고용 영양 정보이며…"
}
```

**실제로 관측된 차단 사유** (실측):

| 사유 | 조건 |
|---|---|
| `normalizer: age 부적합(≥19 필요)` | 미성년 |
| `compliance: 이름 평문 노출` | 이름이 짧아 마스킹이 안 될 때 (`이수` 등 2자) |

### 6.5 Output — 실패(`fail`)

```json
{"status": "fail", "message": "<예외 메시지>", "data": {}}
```

---

## 7. 팀원 백로그(`agent/task_new.md`)와의 대응

| 이 문서 | task_new.md | 상태 |
|---|---|---|
| **D4** Output 구조화 | **T2.3** — aggregator 가 최종 JSON 규격 소유 | ✅ **이미 반영됨** |
| §5 OCR 미구현 | **T3.1** — Upstage Document AI, 키 없으면 stub | ✅ 계획됨 |
| §5 타깃 고정 | **T1.3** — 타깃 선정 하류 이관 | 🔄 진행 중 |
| **§2.1 Input 4필드** | — | ❌ **백로그에 없음** |

### 7.1 D4 는 이미 절반 완료됐습니다

`AggregatedReport` 가 이미 **정본 계약**으로 승격됐습니다
(`models.py:202` 주석: *"★ 최종 리포트 JSON의 정본(canonical) 계약 — 소유자는
aggregator 노드"*).

**필드명은 그대로입니다** — `user_profile` `calculated_target` `timing_guidance`
전부 유지됐고 개명이 없습니다. 화면 쪽에서 맞출 것도 없습니다.

**남은 것은 §3.3 하나** — compliance 가 그 값을 `final_report` 로 넘겨주는 일입니다.

### 7.2 Input 확장이 백로그에 없습니다 ★

**T0~T3 어디에도 `recommend` 입력 필드 추가가 없습니다.** 출력(T2.3)과
OCR(T3.1)은 계획돼 있는데, **영양제·복용약·검진수치를 받는 통로**가 빠져 있습니다.

이게 없으면 T2.3 로 구조화 JSON 을 잘 만들어도 **담을 내용이 없습니다** —
지금 리포트가 누구에게나 같은 4개 영양소를 돌려주는 이유입니다.

**백로그 추가를 요청드립니다.** 작업량은 §2.2 의 붙여넣기 코드가 전부입니다.
