## 실행 방법
# mcp / agent / frontend2 세 개의 서버가 기동되어야 한다.
# 아래 기준은 현재 폴더가 my_hub2 에 위치해야 함.
# 예시) ...\my_hub2> 
# 한 줄 씩 복사해서 터미널에서 실행 할 것.
# 1. mcp
cd mcp
uv sync
uv run server.py

# 2. agent
cd agent
uv sync
uv run server.py

# 3. frontend2
cd frontend2
uv sync
uv run server.py
