"""
telebot 허브 진입점
실행: python main.py
"""
import asyncio
import logging
import os
import signal
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from telebot.handlers import system, project
from telebot.monitor import Monitor
from telebot.registry import load_global_config, GlobalConfig
from telebot.web import start_web_server

load_dotenv()

PID_FILE = Path.home() / ".telebot" / "telebot.pid"


def _check_and_write_pid() -> None:
    """이미 실행 중인 인스턴스가 있으면 종료시키고 현재 PID를 기록"""
    if PID_FILE.exists():
        old_pid = PID_FILE.read_text().strip()
        try:
            os.kill(int(old_pid), signal.SIGTERM)
        except (ProcessLookupError, ValueError):
            pass
    PID_FILE.write_text(str(os.getpid()))


def _cleanup_pid() -> None:
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

WEB_PORT = int(os.environ.get("TELEBOT_WEB_PORT", "8080"))


def _build_auth_filter(chat_id: str) -> filters.BaseFilter:
    """허가된 chat_id만 통과시키는 필터"""
    allowed_ids = {int(cid.strip()) for cid in chat_id.split(",") if cid.strip()}

    class AuthFilter(filters.MessageFilter):
        def filter(self, message) -> bool:  # type: ignore[override]
            return message.chat_id in allowed_ids

    return AuthFilter()


async def _post_init(application: Application) -> None:
    """봇 시작 후 웹 서버를 asyncio task로 실행"""
    monitor: Monitor = application.bot_data["monitor"]
    asyncio.create_task(start_web_server(monitor, port=WEB_PORT))


def main() -> None:
    _check_and_write_pid()
    import atexit
    atexit.register(_cleanup_pid)

    config: GlobalConfig = load_global_config()
    if not config.bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 환경변수 또는 ~/.telebot/config.yml 설정이 필요합니다.")

    monitor = Monitor()
    auth_filter = _build_auth_filter(config.chat_id)

    app = (
        Application.builder()
        .token(config.bot_token)
        .post_init(_post_init)
        .build()
    )
    app.bot_data["config"] = config
    app.bot_data["monitor"] = monitor

    # 시스템 핸들러
    app.add_handler(CommandHandler("list",       system.cmd_list,       filters=auth_filter))
    app.add_handler(CommandHandler("select",     system.cmd_select,     filters=auth_filter))
    app.add_handler(CommandHandler("deselect",   system.cmd_deselect,   filters=auth_filter))
    app.add_handler(CommandHandler("help",       system.cmd_help,       filters=auth_filter))
    app.add_handler(CommandHandler("start",      system.cmd_help,       filters=auth_filter))
    app.add_handler(CommandHandler("register",   system.cmd_register,   filters=auth_filter))
    app.add_handler(CommandHandler("unregister", system.cmd_unregister, filters=auth_filter))
    app.add_handler(CommandHandler("cmds",       system.cmd_cmds,       filters=auth_filter))
    app.add_handler(CommandHandler("addcmd",     system.cmd_addcmd,     filters=auth_filter))
    app.add_handler(CommandHandler("delcmd",     system.cmd_delcmd,     filters=auth_filter))

    # 프로젝트 명령 핸들러 (/proj 및 컨텍스트 라우팅)
    app.add_handler(
        MessageHandler(filters.TEXT & auth_filter, project.handle_message)
    )

    logger.info("telebot 허브 시작. 등록된 프로젝트: %s", list(config.projects.keys()))
    logger.info("대시보드: http://localhost:%d", WEB_PORT)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
