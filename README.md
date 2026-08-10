## 📁 프로젝트 구조 (Monorepo)

본 레포지토리는 하나의 루트 내에 다중 프로젝트가 포함된 모노레포 구조로 구성함.
각 폴더가 독립된 하나의 별도 프로젝트이므로, 가상 환경 및 패키지 구성도 각 하위 폴더에서 함에 주의할 것.
(상세 설정 내용은 각 하위 폴더의 README.md 참고)

```text
myhub2/ (Repository Root)
├── backend/          # 백엔드 프로젝트 폴더
├── frontend/         # 프론트엔드 프로젝트 폴더
└── mcp/              # ◀ 현재 프로젝트 (MCP 서버)
    ├── .venv/        # 격리된 Python 3.11 가상환경
    ├── pyproject.toml # 의존성 및 Python 3.11 버전 명세
    ├── uv.lock       # 버전 잠금 파일 (팀원 공통 버전 고정)
    └── server.py     # MCP 서버 메인 소스 코드
```
