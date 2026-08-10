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

## ⚙️ 제공하는 핵심 MCP 도구(Tools) 명세

### 1. `calculate_precision_nutrition` (체중당 영양소 섭취 산출)
* **설명**: 임상 Mifflin-St Jeor 수식을 기반으로 사용자의 기초대사량(BMR), 일일 총 에너지 소비량(TDEE), 탄단지(60:15:25) 그람수, 비타민 B군 및 생애주기별 미크로 영양소를 산출.
* **신체 정보 누락 처리**: 만약 연령, 체중, 신장 정보가 입력되지 않을 경우 가이드북 성인 기본 표준 데이터셋(**40세, 80kg, 175cm, 2400kcal 환경**)을 안전 자동 적용하도록 셋팅했음.

### 2. `normalize_supplement_component` (KDRI 코드 기반 단위 검증 및 환산)
* **설명**: 영양소 표준 코드(`nutrient_code`)와 현재 영양제 라벨의 수치/단위를 입력받아 표준 규격과 일치하는지 Boolean(`is_unit_matched`) 검증합니다.
* **자동 환산 지원**: 
  * 비타민D (`IU` ➔ `μg` 공식 환산)
  * 비타민A (`IU` ➔ `μg RAE` 공식 환산)
  * 비타민E (`IU` ➔ `mg α-TE` 공식 환산)
  * 무게 스케일 보정 (`g` ➔ `mg`, `mg` ➔ `μg` 등)
