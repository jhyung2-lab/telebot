"""
모니터링 모듈: 봇 이벤트를 메모리 버퍼, 파일, WebSocket으로 동시에 기록
"""
import asyncio
import json
import uuid
from collections import deque
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

LOGS_DIR = Path.home() / ".telebot" / "logs"


class LogEvent(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    ts: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="milliseconds"))
    direction: str          # "in" | "out"
    chat_id: int = 0
    text: str = ""          # 사용자 입력 원문
    project: Optional[str] = None
    command: Optional[str] = None
    command_run: Optional[str] = None   # 실제 실행 shell 명령 or "METHOD /path"
    project_path: Optional[str] = None  # 프로젝트 절대 경로
    result: Optional[str] = None        # 봇 응답 텍스트
    duration_ms: Optional[float] = None
    error: Optional[str] = None


class Monitor:
    def __init__(self) -> None:
        self._buffer: deque[LogEvent] = deque(maxlen=500)
        self._ws_clients: set = set()
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def _log_path(self) -> Path:
        return LOGS_DIR / f"{date.today().isoformat()}.jsonl"

    async def record(self, event: LogEvent) -> None:
        self._buffer.append(event)
        self._write_to_file(event)
        await self._broadcast(event)

    def _write_to_file(self, event: LogEvent) -> None:
        try:
            with self._log_path().open("a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
        except OSError:
            pass

    async def _broadcast(self, event: LogEvent) -> None:
        if not self._ws_clients:
            return
        payload = event.model_dump_json()
        dead: set = set()
        for ws in self._ws_clients:
            try:
                await ws.send_str(payload)
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead

    def add_ws(self, ws) -> None:
        self._ws_clients.add(ws)

    def remove_ws(self, ws) -> None:
        self._ws_clients.discard(ws)

    def recent(self, n: int = 200) -> list[dict]:
        events = list(self._buffer)[-n:]
        return [e.model_dump() for e in events]
