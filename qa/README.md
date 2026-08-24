# qa — 리포트 품질 점검

지시사항 4번(테스트 시나리오 · 품질 확인 · 개선 · 비교자료)의 작업 폴더입니다.
`frontend2` 의 판정 엔진을 **읽기만** 하고, 개선할 때만 그쪽 코드를 고칩니다.

## 실행

```
cd qa
python run_local.py       # 케이스 4개 채점 -> out/before/
python run_local.py --after   # 개선 후 -> out/after/
python coverage.py        # 입력 반영률 -> out/coverage.md
```

DB · 에이전트 · mcp · 로그인 **전부 필요 없습니다.**
`analyze.py` · `exam.py` · `standards.py` 가 표준 라이브러리에만 의존하므로
별도 venv 없이 그냥 `python` 으로 돌아갑니다.

> Windows 콘솔이 CP949 라서 출력이 깨지면 `PYTHONIOENCODING=utf-8` 을 앞에 붙이세요.
> 결과 파일은 항상 UTF-8 로 저장되므로 파일 쪽은 영향이 없습니다.

## 구성

```
cases/
  case1_normal.json       검진 정상 · 영양제 없음
  case2_overlap.json      상한 초과 + 성분 중복
  case3_interaction.json  약물–성분 상호작용
  case4_edge.json         경계값 · 결측 · 환산 실패   ★ brittle
  case5_full_exam.json    검진 40키 전부 (고령 종합검진)
  expected.json           손으로 계산한 정답
  review.md               검토 기록 (지시 4-1 의 '검토해볼 것')
engine.py                 frontend2 엔진 로더 (sys.path 처리는 여기 한 곳)
run_local.py              채점 + 스냅샷
coverage.py               입력 반영률 산출
baseline_standards.json   기준값 지문 (자동 생성)
out/before · out/after    케이스별 JSON · HTML · score.md
report/comparison.html    개선 전후 비교 (지시 4-4)
```

## 기대값을 손으로 계산하는 이유

`expected.json` 은 엔진을 돌려서 만든 값이 아니라, `standards.py` 의 `STD_LIST` 와
`exam.py` 의 임계값을 보고 **사람이 계산한** 값입니다.

엔진 출력으로 기대값을 만들면 엔진의 버그를 그대로 따라가서 항상 통과하는
무의미한 테스트가 됩니다. 실제로 이 과정에서 초안 기대값 3건이 틀렸다는 것을
찾아냈습니다(엔진이 맞았습니다). 근거는 `cases/review.md` 에 있습니다.

## 기준값이 바뀌면

`run_local.py` 는 실행할 때마다 현재 `STD_LIST` 를 `baseline_standards.json` 과
대조합니다. 달라진 항목이 있으면 `score.md` 맨 위에 이렇게 알려 줍니다.

```
## ⚠ 기준값이 바뀌었습니다
- 비타민 D: ul 100 → 150
```

테스트 실패와 기준값 변경을 구분하기 위한 것입니다. 이 표시가 뜨면
`expected.json` 을 다시 검토해야 합니다.

`case4` 만 `"brittle": true` 입니다. 마그네슘 350mg = 상한 350, 엽산 1000µg = 상한 1000
으로 **상한과 정확히 같은 값**이라 기준이 바뀌면 반드시 깨집니다. 버그가 아니라
경계 이동을 감시하기 위한 의도된 설계입니다.

## 지금까지의 결과

| | |
|---|---|
| 판정 정확성 | **123/123 통과** — 계산 오류 없음 |
| 입력 반영률 | **14–21%** — 영양제·약·검진이 리포트에 전달되지 않음 |
| 개선 | 이미 계산된 판정을 화면에 함께 표시 (안내 29건 복구) |

자세한 내용은 `report/comparison.html` 을 여세요.


## 무엇을 얼마나 덮고 있나

케이스가 실제로 건드리는 범위입니다. `case5` 를 넣고 다시 잰 값입니다.

| 축 | 최대치 | 케이스가 쓰는 것 | |
|---|---|---|---|
| 검진 항목 | 40키 | **40키** | 전부 |
| 검진 그룹 | 14그룹 | **14그룹** | 전부 |
| 성분 기준값 | 18종 | 9종 | 절반 |
| 약물–성분 규칙 | 8건 | 2건 | 와파린 2건만 |
| 나이 | — | 35 · 45 · 58 · 62 · 71 | |

### 남아 있는 구멍 두 개

**성분 9종이 한 번도 안 나옵니다** — 비타민 B1 · B2 · 나이아신 · B6 · B12 ·
비타민 E · 철 · 셀레늄 · 루테인. `case5` 는 영양제를 먹지 않는 사람이라
식사 추정치로만 계산되어 이 축을 넓히지 못합니다.

**약물 규칙 6건이 한 번도 안 걸립니다** — 레보티록신↔칼슘 · 레보티록신↔철 ·
메트포르민↔비타민 B12 · 테트라사이클린↔칼슘 · 테트라사이클린↔아연 ·
스타틴↔나이아신. 지금 케이스에 있는 약은 와파린 하나뿐입니다.

둘 다 **다약제 복용 케이스 하나**(예: 갑상선약 + 당뇨약 + 스타틴을 함께 먹으며
종합비타민·철분제를 복용)면 대부분 덮입니다. 기대값을 손으로 계산해야 하므로
별도 작업으로 남겨 둡니다.

## case5 — 검진 40키

기존 네 케이스는 혈액검사 계열(혈압·비만·빈혈·당뇨·이상지질·간장·신장)만
쓰고 있었습니다. 기능검사·문진 계열 5개 그룹은 한 번도 실행되지 않았습니다.

```
노인 신체기능    leg balC balO
정신건강·인지    phq9 phq9q9 capeF capeD kdsq
청력           pta whisper
만성폐쇄성폐질환  ratio fev1 fvc
구강           caries suspect filled lost gingiva calculus plaque
```

`case5` 가 이 22개 키를 포함해 40키를 전부 채웁니다. 판정 대상은 34개 항목입니다
— 혈압(sbp+dbp) · BMI(height+weight) · PHQ-9(phq9+phq9q9) · CAPE-15(capeF+capeD) ·
폐기능(ratio+fev1+fvc)은 여러 입력을 한 줄로 묶기 때문입니다.

> 이 사각지대는 테스트 밖으로도 번졌습니다. `schema/superset.json` 의
> `ExamValues` 가 19개뿐인데, 런타임 표본(= 이 케이스들)에서 추출했기
> 때문입니다. 그 누락이 `agent/schemas/models.py` 의 `ExamValues` 로
> 그대로 옮겨 갔습니다.
