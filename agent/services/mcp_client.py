import os
import aiohttp
from typing import Any, Dict, List

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8080")

async def call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """
    http://localhost:8080에 구동중인 로컬 MCP 서버로 JSON-RPC 2.0 규격에 맞는 Tool Call을 보냅니다.
    """
    payload = {
        "jsonrpc": "2.0",
        "method": f"tools/{tool_name}",
        "params": arguments,
        "id": 1
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{MCP_SERVER_URL}/", json=payload, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "error" in data:
                        raise RuntimeError(f"MCP Tool error: {data['error']}")
                    return data.get("result")
                else:
                    text = await resp.text()
                    raise RuntimeError(f"MCP server HTTP error: {resp.status} - {text}")
    except Exception as e:
        print(f"[MCP Warning] {tool_name} 호출 중 예외 발생, fallback 연산 수행: {str(e)}")
        # 로컬 서버 미구동 시의 Fallback 연산을 위한 예외 전파
        raise e
