"""
type=command 프로젝트의 명령을 subprocess로 실행하고 결과를 반환
"""
import asyncio
from pathlib import Path

from telebot.registry import CommandSpec


MAX_OUTPUT_LENGTH = 4000  # 텔레그램 메시지 한계(4096)보다 여유있게 설정


async def run_command(cmd: CommandSpec, cwd: Path) -> str:
    """shell 명령을 실행하고 stdout+stderr를 합쳐 반환. 타임아웃 초과 시 오류 메시지 반환."""
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd.run,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=cmd.timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return f"⏱ 타임아웃: {cmd.timeout}초 초과"

        output = stdout.decode("utf-8", errors="replace").strip()
        if not output:
            return f"✅ 완료 (종료코드: {proc.returncode})"

        if len(output) > MAX_OUTPUT_LENGTH:
            output = output[:MAX_OUTPUT_LENGTH] + "\n\n...출력이 잘렸습니다"

        prefix = "✅" if proc.returncode == 0 else f"❌ (종료코드: {proc.returncode})"
        return f"{prefix}\n```\n{output}\n```"

    except Exception as e:
        return f"❌ 실행 오류: {e}"
