# Reviewer Agent 판단 기준

Executor 결과를 검수해 다음 두 원인으로 라우팅한다. 재시도는 최대 **3회**
(`State.retry_count` 누적). 3회 소진 후에도 실패하면 해당 항목만 **부분 실패
(partial_failure)**로 확정하고 파이프라인은 중단 없이 Aggregator로 진행한다.

| 상황 | 원인 판단 | 라우팅 |
|---|---|---|
| MCP 툴 호출 자체가 에러/타임아웃 (`status == "error"`) | 실행(Executor) 문제 | `reject_to_executor` |
| 툴은 정상 응답했으나 결과값이 UL 상한 초과 (`is_safe == false` 또는 `ul_violations` 존재) | 계획(Planner)에서 잘못된 툴/파라미터 선택 가능성 | `reject_to_planner` |
| 위반 없음 | — | `pass` (Aggregator로) |

## 부분 실패 처리
- 실패 항목: `{step, tool_name, status: "failed", reason}` 형태로 `State.failed_items`에 기록.
- 성공 항목은 정상 결과로 함께 전달.
- Compliance 최종 응답에는 요약 안내 문구만 노출(기술적 세부사항 비노출):
  > "일부 항목은 자동 검증을 완료하지 못해 이번 결과에서 제외되었습니다.
  > 해당 항목은 전문가와 상담하시기를 권장드립니다."

## 우선순위
툴 에러와 UL 위반이 동시 존재하면 **툴 에러(executor)** 를 먼저 처리한다.
(계획을 고쳐도 실행이 깨져 있으면 무의미하므로.)
