# 1. 프로젝트 폴더로 이동 (...workspace\nvidia-pjt\source\my_hub2\agent> 와 같이 최종적으로 프롬프트가 \my_hub2\agent> 가 되면 됩니다)
cd my_hub2/agent

# 2. Python 3.11 기반 가상환경 생성 (my_hub2/agent 폴더 하위에 .venv가 없다면 실행할 것)
# uv venv --python 3.11

# 3. 가상환경 활성화
# Windows 는 아래 실행
# .venv\Scripts\activate

# macOS / Linux 는 아래 실행
# source .venv/bin/activate

# 4. 프로젝트 의존성 설치
uv sync

# 5. RAG 데이터 준비
# agent/data 폴더에 PDF, CSV 등의 파일이 있는지 확인하고, rag_store 폴더가 없다면 아래 명령어 실행
# uv run rag_ingest.py

# 6. 서버 실행
uv run server.py
