"""
핵심 라우팅: 텔레그램 명령을 파싱해 올바른 프로젝트/executor로 dispatch
"""
import time
from pathlib import Path
from typing import Optional

from telebot import session
from telebot.executor.command import run_command
from telebot.registry import GlobalConfig, load_project_spec, ProjectSpec


async def dispatch(
    chat_id: int,
    project_name: str,
    cmd_name: str,
    config: GlobalConfig,
    monitor=None,
) -> str:
    """프로젝트와 명령명으로 실행을 위임하고 결과 문자열을 반환"""
    project_path = config.projects.get(project_name)
    if project_path is None:
        return f"❌ 프로젝트 '{project_name}'이 등록되어 있지 않습니다. /list 로 확인하세요."

    try:
        spec: ProjectSpec = load_project_spec(project_path)
    except FileNotFoundError as e:
        return f"❌ {e}"

    cmd_spec = spec.commands.get(cmd_name)
    if cmd_spec is None:
        available = ", ".join(spec.commands.keys()) or "없음"
        return f"❌ 명령 '{cmd_name}'을 찾을 수 없습니다.\n사용 가능: {available}"

    session.touch(chat_id)

    # 실제로 실행될 명령 문자열 (로그용)
    command_run: Optional[str] = None
    result: str = ""
    error: Optional[str] = None
    start = time.monotonic()

    try:
        if spec.type == "command":
            command_run = cmd_spec.run
            result = await run_command(cmd_spec, project_path)
        elif spec.type == "agent":
            command_run = f"{cmd_spec.method} {cmd_spec.path}"
            from telebot.executor.agent import call_agent
            result = await call_agent(spec, cmd_spec)
        else:
            result = f"❌ 알 수 없는 프로젝트 타입: {spec.type}"
    except Exception as e:
        error = str(e)
        result = f"❌ 내부 오류: {e}"

    duration_ms = (time.monotonic() - start) * 1000

    if monitor is not None:
        from telebot.monitor import LogEvent
        await monitor.record(LogEvent(
            direction="out",
            chat_id=chat_id,
            project=project_name,
            command=cmd_name,
            command_run=command_run,
            project_path=str(project_path),
            result=result,
            duration_ms=round(duration_ms, 1),
            error=error,
        ))

    return result


async def route_message(chat_id: int, text: str, config: GlobalConfig, monitor=None) -> str | None:
    """
    텍스트 메시지를 파싱해 dispatch 결과를 반환.
    처리 불가한 메시지면 None 반환.

    지원하는 형식:
      /proj <project> <cmd>   — 직접 지정
      /<cmd>                  — 세션 컨텍스트의 프로젝트로 라우팅
    """
    text = text.strip()

    # /proj <project> <cmd>
    if text.startswith("/proj "):
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            return "사용법: /proj <프로젝트명> <명령>"
        _, project_name, cmd_name = parts[0], parts[1], parts[2]
        return await dispatch(chat_id, project_name, cmd_name, config, monitor)

    # /<cmd> — 컨텍스트 라우팅
    if text.startswith("/"):
        cmd_name = text[1:].split()[0]
        # 시스템 명령은 handlers/system.py에서 처리하므로 여기선 넘김
        system_cmds = {"list", "select", "help", "proj", "register", "unregister",
                       "addcmd", "delcmd", "cmds", "start", "deselect"}
        if cmd_name in system_cmds:
            return None

        project_name = session.get_project(chat_id)
        if project_name is None:
            return "프로젝트가 선택되어 있지 않습니다. /list 로 목록을 확인하고 /select <프로젝트명> 으로 선택하세요."
        return await dispatch(chat_id, project_name, cmd_name, config, monitor)

    return None
