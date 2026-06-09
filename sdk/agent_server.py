"""
AgentServer: type=agent 프로젝트에서 재사용하는 경량 asyncio HTTP 서버.

사용 예시 (auto_trading/agent_server.py):

    from sdk.agent_server import AgentServer

    server = AgentServer(port=18001)

    @server.route("GET", "/status")
    async def get_status():
        return {"trading": True, "market": "open"}

    @server.route("POST", "/begin")
    async def post_begin():
        start_trading()
        return {"ok": True, "message": "자동매매 시작"}

    # 메인 루프에서 백그라운드로 실행
    await server.start()
    # 또는 동기 코드에서:
    import asyncio
    asyncio.get_event_loop().run_until_complete(server.start())
"""
import asyncio
import json
import logging
from typing import Callable, Awaitable, Any

logger = logging.getLogger(__name__)

Handler = Callable[[], Awaitable[Any]]


class AgentServer:
    def __init__(self, port: int = 18001, host: str = "127.0.0.1") -> None:
        self.port = port
        self.host = host
        self._routes: dict[tuple[str, str], Handler] = {}

    def route(self, method: str, path: str) -> Callable:
        """라우트 데코레이터"""
        def decorator(func: Handler) -> Handler:
            self._routes[(method.upper(), path)] = func
            return func
        return decorator

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = (await reader.readline()).decode().strip()
            if not request_line:
                writer.close()
                return

            parts = request_line.split()
            method, path = parts[0], parts[1] if len(parts) > 1 else "/"

            # 헤더 소비 (바디는 현재 미사용)
            while True:
                line = (await reader.readline()).decode().strip()
                if not line:
                    break

            handler = self._routes.get((method, path))
            if handler is None:
                body = json.dumps({"error": f"Not Found: {method} {path}"})
                status = "404 Not Found"
            else:
                try:
                    result = await handler()
                    body = json.dumps(result, ensure_ascii=False)
                    status = "200 OK"
                except Exception as e:
                    body = json.dumps({"error": str(e)})
                    status = "500 Internal Server Error"
                    logger.exception("핸들러 오류: %s %s", method, path)

            response = (
                f"HTTP/1.1 {status}\r\n"
                f"Content-Type: application/json; charset=utf-8\r\n"
                f"Content-Length: {len(body.encode())}\r\n"
                f"Connection: close\r\n\r\n"
                f"{body}"
            )
            writer.write(response.encode())
            await writer.drain()
        except Exception:
            logger.exception("요청 처리 오류")
        finally:
            writer.close()

    async def start(self) -> None:
        server = await asyncio.start_server(self._handle, self.host, self.port)
        logger.info("AgentServer 시작: %s:%d", self.host, self.port)
        async with server:
            await server.serve_forever()

    def start_background(self, loop: asyncio.AbstractEventLoop | None = None) -> asyncio.Task:
        """현재 이벤트 루프에서 백그라운드 태스크로 실행"""
        lp = loop or asyncio.get_event_loop()
        return lp.create_task(self.start())
