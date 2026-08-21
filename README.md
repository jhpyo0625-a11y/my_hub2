## 실행 방법
# mcp / agent / frontend2 세 개의 서버가 기동되어야 한다.
# 아래 기준은 현재 폴더가 my_hub2 에 위치해야 함.
# 예시) ...\my_hub2> 
# 한 줄 씩 복사해서 터미널에서 실행 할 것.

# 1. mcp
# 폴더 이동 (현재 폴더가 my_hub2 일 때)
cd mcp
# 패키지 상태 동기화
uv sync
# 서버 기동
uv run server.py


# 2. agent
# 폴더 이동 (현재 폴더가 my_hub2 일 때)
cd agent
# 패키지 상태 동기화
uv sync
# 서버 기동
uv run server.py

# 3. frontend2
# 폴더 이동 (현재 폴더가 my_hub2 일 때)
cd frontend2
# 패키지 상태 동기화
uv sync
# 서버 기동
uv run server.py
