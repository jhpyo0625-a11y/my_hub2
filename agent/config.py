"""agent/.env를 읽어 설정 상수로 노출하는 단일 지점.

모든 모듈은 os.getenv 대신 여기서 값을 import한다.
빈 값("")은 기본값으로 폴백.
"""
from pathlib import Path

from dotenv import dotenv_values

_env = dotenv_values(Path(__file__).resolve().parent / ".env")


def _get(key: str, default: str | None = None) -> str | None:
    value = _env.get(key)
    return value if value else default


OPENAI_MODEL = _get("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_API_KEY = _get("OPENAI_API_KEY")
OPENAI_BASE_URL = _get("OPENAI_BASE_URL")
DATABASE_URL = _get("DATABASE_URL")
MCP_SERVER_URL = _get("MCP_SERVER_URL", "http://localhost:8080")
MAX_RETRIES = int(_get("MAX_RETRIES", "3"))
