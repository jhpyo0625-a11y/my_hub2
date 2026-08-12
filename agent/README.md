## 0. RAG 임베딩 실행. (이미 임베딩 된 데이터 있으면 실행 불필요.)
# 경로
cd my_hub2/agnet

# 패키지 설치. (이미 있다면 생략)
uv add chromadb sentence-transformers pymupdf

# 데이터 파일 확인. 
# agent 폴더 하위에 data 폴더가 있고 그 하위에 파일들이 존재해야 함.
# 현재 pdf, csv 등 파일만 처리 중.

# 실행.
uv run rag_ingets.py

# 결과.
# rag_store 폴더가 생성되어 하위에 임베딩된 데이터가 존재.


## 1. main 실행.
# 경로 (...workspace\nvidia-pjt\source\my_hub2\agent> 와 같이 최종적으로 \my_hub2\agent> 가 되면 됩니다.)
cd my_hub2/agent

# Python 3.11 기반의 가상환경 생성 (이미 생성했다면 생략)
uv venv --python 3.11

# 가상환경 활성화 
# (macOS/Linux 일 경우)
source .venv/bin/activate
# (Windows 열 경우)
.venv\Scripts\activate

# langgraph 패키지 설치
uv add install langgraph

# 실행
uv run main.py