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
| 판정 정확성 | **68/68 통과** — 계산 오류 없음 |
| 입력 반영률 | **14–21%** — 영양제·약·검진이 리포트에 전달되지 않음 |
| 개선 | 이미 계산된 판정을 화면에 함께 표시 (안내 29건 복구) |

자세한 내용은 `report/comparison.html` 을 여세요.
