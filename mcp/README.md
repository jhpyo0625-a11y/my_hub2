## 🛠️ 개발 환경 구축 및 초기화 (팀원 공통)
패키지 및 가상환경 관리를 가속화하기 위해 최신 파이썬 도구인 `uv`를 사용하며, 안정적인 상용 배포를 위해 **Python 3.11** 환경으로 강제 고정함.

### 1. `uv` 도구 설치
터미널에서 본인의 운영체제에 맞는 명령어를 실행할 것.
* **Windows (PowerShell)**:
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh | iex"
  ```
* **Mac / Linux**:
  ```bash
  curl -LsSf https://astral.sh | sh
  ```
> ⚠️ **주의**: 설치 완료 후, 터미널 설정을 반영하기 위해 **VS Code 터미널 창을 완전히 닫았다가 새로 열기.**

### 2. 프로젝트 진입 및 의존성 동기화
`uv.lock` 기반으로 팀원 전체가 토씨 하나 틀리지 않고 동일한 환경을 구성하는 원클릭 동기화 명령어.
```powershell
# 1. 내 작업 공간인 mcp 폴더로 진입 (★루트에서 작업 금지)
cd myhub2/mcp

# 2. 파이썬 3.11 다운로드, 가상환경(.venv) 빌드 및 패키지 클린 설치
uv sync
```

### 3. 가상환경 활성화 (필수)
패키지 추가나 개발자 도구를 실행하기 전에 가상환경을 항상 활성화해 줍니다.
* **Windows**: `.venv\Scripts\activate`
* **Mac / Linux**: `source .venv/bin/activate`

---

## 🚀 로컬 테스트 및 디버깅 방법 (Inspector)

서버 코드가 정상 작동하는지 외부 에이전트 연동 전 브라우저 UI 환경에서 미리 검증할 수 있음.

### FastMCP 공식 내장 인스펙터 구동
`mcp` 가상환경이 활성화된 상태에서 아래 명령어를 수행합니다.
```powershell
uv run fastmcp dev inspector server.py
```
* **테스트 방법**: 터미널에 출력되는 로컬 웹 주소(`http://localhost:3000` 등)로 접속한 후, 대시보드 화면에 노출되는 두 가지 핵심 툴을 테스트.

---

## 🔒 설계 원칙 (반드시 준수)
이 서버는 **숫자를 스스로 만들지 않습니다.** 모든 수치는 `../backend/src/kdri`의
결정론적 엔진(`compute_report`)이 계산하며, 각 값은 KDRI 2025 vendor 표 또는
출처가 명시된 curated 파일로 추적됩니다. 이것이 제품의 핵심 규칙입니다
(`../CLAUDE.md` 참고).
* **체중/BMR 기반 산출 없음** — 2025 기준의 비타민·무기질 항목에는 체중 기반 값이 없습니다.
* **성별은 필수** — 기본값을 적용하지 않습니다 (철 여성 12mg ≠ 남성 8mg).
* **추측 대신 UNKNOWN** — 국민 평균 식이 기여 자료가 없는 항목은 숫자를 제시하지 않습니다.
* 엔진 로직은 `mcp/`를 import하지 않습니다 (신뢰 경계 TB-1). 이 서버가 엔진을 단방향으로 감쌉니다.

테스트: `PYTHONPATH=../backend/src python test_server.py` (fastmcp 없이 툴 로직 검증)

## ⚙️ 제공하는 핵심 MCP 도구(Tools) 명세

### 1. `analyze_intake_against_kdri` (KDRI 엔진 분석)
* **설명**: 성인 프로필(나이·성별, 선택적으로 복용 영양제·약·검진 수치)을 받아 실제
  엔진을 돌리고, 영양소별 **목표 섭취량(국가 기준 band)**, 식품/보충제 기여, 부족량,
  상한 여유, 추천 보충량을 반환합니다. 검진 수치는 우선순위만 조정하고 목표를 바꾸지 않습니다.
* **거부(refusal) 동작**: `sex`(M/F) 필수 — 없으면 계산하지 않고 거부. `age`는 19세 이상.
  범위를 벗어나면 숫자를 만들지 않고 거부 사유를 반환합니다.

### 2. `normalize_supplement_component` (KDRI 표준 단위 환산)
* **설명**: 영양소 코드와 라벨 수치/단위를 받아 KDRI 표준 단위와 비교·환산합니다.
  표준 단위는 하드코딩 표가 아니라 **실제 nutrient profiles에서 읽습니다**(단일 진실 공급원).
* **환산(각 factor는 코드에 출처 주석 명시)**:
  * 비타민 D `IU` ➔ `µg` (1 µg = 40 IU)
  * 비타민 A `IU` ➔ `µg RAE` (1 µg RAE = 3.33 IU)
  * 비타민 E `IU` ➔ `mg α-TE` (1 mg α-TE = 1.49 IU)
  * 질량 스케일 (`g` ➔ `mg` ➔ `µg`)
  * 정의되지 않은 환산은 임의로 하지 않고 경고로 반환합니다.
