from typing import Any, Dict

from fastmcp import Client

from config import MCP_SERVER_URL

# FastMCP streamable-http 엔드포인트. MCP_SERVER_URL 뒤에 /mcp/ 경로를 붙인다.
_MCP_ENDPOINT = MCP_SERVER_URL.rstrip("/") + "/mcp/"


async def call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """로컬 MCP 서버(FastMCP)의 tool을 표준 MCP 프로토콜로 호출.

    구조화 출력(tool이 반환한 dict)을 그대로 돌려준다.
    서버 미구동/tool 오류 시 예외를 전파해 상위(executor)가 fallback 하도록 한다.
    """
    try:
        async with Client(_MCP_ENDPOINT) as client:
            result = await client.call_tool(tool_name, arguments)
            return result.data
    except Exception as e:
        print(f"[MCP Warning] {tool_name} 호출 중 예외 발생, fallback 연산 수행: {str(e)}")
        raise e
