# dbcheck — 회원 API · DB 연동 점검

지시사항 2(회원가입 API) · 3(로그인 API) · 4(DB 연동 체크)의 검증 폴더입니다.
구현 코드는 지시대로 **기존 서버에 추가**했고(`agent/`), 이 폴더에는
검증 스크립트와 산출물만 둡니다.

## 실행

에이전트의 가상환경이 필요합니다(psycopg·bcrypt).

```
cd agent
uv run python ../dbcheck/check_db.py      # DB 연동 점검
uv run python ../dbcheck/test_auth.py     # 회원 저장/조회 (DB 직접)
uv run python ../dbcheck/test_api.py      # REST API (:8000 기동 필요)
cd ../dbcheck && python make_listing.py   # 연동 지점 목록 -> out/listing.csv
```

> 콘솔이 CP949 라 한글이 깨지면 `PYTHONIOENCODING=utf-8` 을 앞에 붙이세요.
> 결과 파일은 항상 UTF-8 로 저장되므로 파일 쪽은 영향이 없습니다.

## 구성

```
check_db.py        접속·테이블·데이터·쿼리·MCP 6단 점검
test_auth.py       db_helper 회원 함수 검증 (27항목)
test_api.py        REST API 검증 (17항목)
make_listing.py    연동 지점 전수 목록 생성
out/
  result.json/csv  check_db 결과
  listing.csv/json 연동 지점 목록 (구글 시트용)
```

## 테스트 계정 정책

실제 공유 DB(Neon)에 씁니다. 계정은 전부 `qa_test_` 로 시작하게 만들고,
스크립트가 끝날 때 `finally` 에서 지웁니다. 중간에 실패해도 정리됩니다.
검증 후 `users` 는 0행으로 복구됩니다.

## 왜 check_db.py 가 따로 필요한가

`agent/nodes/executor.py` 는 `MCP → DB 직접조회 → 결정적 stub` 3단으로
떨어지면서 예외를 전부 삼킵니다. **DB 가 완전히 끊겨 있어도 API 는
`status:"success"` 를 돌려줍니다.** 그래서 API 를 불러 보는 것만으로는
연동 여부를 알 수 없고, 각 계층을 직접 찌르는 도구가 필요합니다.

## 현재 결과

| | |
|---|---|
| DB 접속 | 정상 (neondb, 502ms) |
| 테이블 6개 | 전부 존재 |
| 회원가입·로그인 | 구현 완료 · 44항목 통과 |
| 점검 요약 | 정상 21 · 주의 5 · **실패 0** |

자세한 내용은 `out/listing.csv` 와 구글 스프레드시트를 참고하세요.
