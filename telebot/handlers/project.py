"""
프로젝트 명령 핸들러: /proj 및 컨텍스트 기반 /<cmd> 라우팅
"""
from telegram import Update
from telegram.ext import ContextTypes

from telebot.registry import GlobalConfig
from telebot.router import route_message


def _get_config(context: ContextTypes.DEFAULT_TYPE) -> GlobalConfig:
    return context.application.bot_data["config"]


def _get_monitor(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data.get("monitor")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """모든 텍스트 메시지를 받아 router에 위임"""
    if not update.message or not update.message.text:
        return

    config = _get_config(context)
    monitor = _get_monitor(context)
    chat_id = update.effective_chat.id
    text = update.message.text

    # 수신 이벤트 기록
    if monitor is not None:
        from telebot.monitor import LogEvent
        await monitor.record(LogEvent(
            direction="in",
            chat_id=chat_id,
            text=text,
        ))

    result = await route_message(chat_id, text, config, monitor)
    if result is not None:
        await update.message.reply_text(result, parse_mode="Markdown")
