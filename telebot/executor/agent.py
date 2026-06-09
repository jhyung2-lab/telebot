"""
type=agent 프로젝트의 명령을 HTTP로 호출하고 결과를 반환
"""
import json

try:
    import aiohttp
    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False

from telebot.registry import CommandSpec, ProjectSpec

AGENT_TIMEOUT = 30


async def call_agent(spec: ProjectSpec, cmd: CommandSpec) -> str:
    if not _AIOHTTP_AVAILABLE:
        return "❌ aiohttp가 설치되어 있지 않습니다. `pip install aiohttp` 를 실행하세요."

    if not spec.port:
        return f"❌ 프로젝트 '{spec.name}'에 port가 설정되어 있지 않습니다."

    url = f"http://localhost:{spec.port}{cmd.path}"
    method = cmd.method.upper()

    try:
        timeout = aiohttp.ClientTimeout(total=AGENT_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as client:
            async with client.request(method, url) as resp:
                body = await resp.text()
                try:
                    data = json.loads(body)
                    pretty = json.dumps(data, ensure_ascii=False, indent=2)
                    status = "✅" if resp.status < 400 else "❌"
                    return f"{status} `{method} {cmd.path}` ({resp.status})\n```\n{pretty}\n```"
                except json.JSONDecodeError:
                    return f"{'✅' if resp.status < 400 else '❌'} ({resp.status})\n{body}"
    except aiohttp.ClientConnectorError:
        return (
            f"❌ 에이전트에 연결할 수 없습니다. (localhost:{spec.port})\n"
            f"프로젝트 '{spec.name}'이 실행 중인지 확인하세요."
        )
    except Exception as e:
        return f"❌ 오류: {e}"
