# 경로 (...workspace\nvidia-pjt\source\my_hub2\agent> 와 같이 최종적으로 \my_hub2\agent> 가 되면 됩니다.)
cd my_hub2/agent

# Python 3.11 기반의 가상환경 생성
uv venv --python 3.11

# 가상환경 활성화 (macOS/Linux)
source .venv/bin/activate

# 가상환경 활성화 (Windows)
.venv\Scripts\activate

# langgraph 패키지 설치
uv pip install langgraph

# 실행
python main.py