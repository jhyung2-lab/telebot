"""
시스템 명령 핸들러: /list, /select, /deselect, /help, /register, /unregister,
                   /addcmd, /delcmd, /cmds
"""
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from telebot import session
from telebot.registry import (
    GlobalConfig,
    load_project_spec,
    save_global_config,
    save_project_spec,
    CommandSpec,
)


def _get_config(context: ContextTypes.DEFAULT_TYPE) -> GlobalConfig:
    return context.application.bot_data["config"]


def _set_config(context: ContextTypes.DEFAULT_TYPE, config: GlobalConfig) -> None:
    context.application.bot_data["config"] = config


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = _get_config(context)
    if not config.projects:
        await update.message.reply_text("등록된 프로젝트가 없습니다. /register <경로> 로 추가하세요.")
        return

    lines = ["📋 *등록된 프로젝트 목록*\n"]
    current = session.get_project(update.effective_chat.id)
    for name, path in config.projects.items():
        try:
            spec = load_project_spec(path)
            desc = spec.description or ""
            badge = " ◀ 현재 선택" if name == current else ""
            lines.append(f"• `{name}` ({spec.type}) {desc}{badge}")
        except FileNotFoundError:
            lines.append(f"• `{name}` ⚠️ .telebot.yml 없음")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = _get_config(context)
    args = context.args
    if not args:
        await update.message.reply_text("사용법: /select <프로젝트명>")
        return

    name = args[0]
    if name not in config.projects:
        await update.message.reply_text(f"❌ 프로젝트 '{name}'을 찾을 수 없습니다. /list 로 확인하세요.")
        return

    session.set_project(update.effective_chat.id, name)

    try:
        spec = load_project_spec(config.projects[name])
        cmds = ", ".join(f"`/{c}`" for c in spec.commands) or "없음"
        await update.message.reply_text(
            f"✅ *{name}* 선택됨\n사용 가능한 명령: {cmds}",
            parse_mode="Markdown",
        )
    except FileNotFoundError:
        await update.message.reply_text(f"✅ *{name}* 선택됨 (⚠️ .telebot.yml 없음)", parse_mode="Markdown")


async def cmd_deselect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session.clear_project(update.effective_chat.id)
    await update.message.reply_text("프로젝트 선택이 해제되었습니다.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🤖 *telebot 허브 명령 목록*\n\n"
        "*프로젝트 관리*\n"
        "`/list` — 등록된 프로젝트 목록\n"
        "`/register <경로>` — 새 프로젝트 등록\n"
        "`/unregister <이름>` — 프로젝트 등록 해제\n\n"
        "*컨텍스트 선택*\n"
        "`/select <이름>` — 프로젝트 선택 (이후 명령 자동 라우팅)\n"
        "`/deselect` — 선택 해제\n\n"
        "*명령 실행*\n"
        "`/proj <프로젝트> <명령>` — 직접 실행\n"
        "`/<명령>` — 선택된 프로젝트에서 실행\n\n"
        "*명령 관리*\n"
        "`/cmds [프로젝트]` — 명령 목록 조회\n"
        "`/addcmd <프로젝트> <명령> <실행어> [설명]` — 명령 추가\n"
        "`/delcmd <프로젝트> <명령>` — 명령 삭제\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = _get_config(context)
    args = context.args
    if not args:
        await update.message.reply_text("사용법: /register <프로젝트 경로>")
        return

    project_path = Path(args[0]).expanduser().resolve()
    if not project_path.is_dir():
        await update.message.reply_text(f"❌ 디렉토리가 없습니다: {project_path}")
        return

    try:
        spec = load_project_spec(project_path)
    except FileNotFoundError:
        await update.message.reply_text(f"❌ {project_path}/.telebot.yml 파일이 없습니다.")
        return

    config.projects[spec.name] = project_path
    save_global_config(config)
    _set_config(context, config)

    cmds = ", ".join(f"`/{c}`" for c in spec.commands) or "없음"
    await update.message.reply_text(
        f"✅ *{spec.name}* 등록 완료\n설명: {spec.description}\n사용 가능한 명령: {cmds}",
        parse_mode="Markdown",
    )


async def cmd_unregister(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = _get_config(context)
    args = context.args
    if not args:
        await update.message.reply_text("사용법: /unregister <프로젝트명>")
        return

    name = args[0]
    if name not in config.projects:
        await update.message.reply_text(f"❌ 프로젝트 '{name}'을 찾을 수 없습니다.")
        return

    del config.projects[name]
    save_global_config(config)
    _set_config(context, config)

    if session.get_project(update.effective_chat.id) == name:
        session.clear_project(update.effective_chat.id)

    await update.message.reply_text(f"✅ *{name}* 등록 해제됨 (프로젝트 파일은 삭제되지 않음)", parse_mode="Markdown")


async def cmd_cmds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = _get_config(context)
    args = context.args

    if args:
        name = args[0]
    else:
        name = session.get_project(update.effective_chat.id)
        if not name:
            await update.message.reply_text("프로젝트를 선택하거나 /cmds <프로젝트명> 으로 지정하세요.")
            return

    if name not in config.projects:
        await update.message.reply_text(f"❌ 프로젝트 '{name}'을 찾을 수 없습니다.")
        return

    try:
        spec = load_project_spec(config.projects[name])
    except FileNotFoundError as e:
        await update.message.reply_text(f"❌ {e}")
        return

    if not spec.commands:
        await update.message.reply_text(f"*{name}*에 등록된 명령이 없습니다.", parse_mode="Markdown")
        return

    lines = [f"📌 *{name}* 명령 목록 ({spec.type})\n"]
    for cmd_name, cmd in spec.commands.items():
        if spec.type == "command":
            lines.append(f"• `/{cmd_name}` — {cmd.description or cmd.run}")
        else:
            lines.append(f"• `/{cmd_name}` [{cmd.method}] {cmd.path} — {cmd.description}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_addcmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /addcmd <project> <name> <run_or_method_path> [description]
    type=command:  /addcmd public_api report "python report.py" "월간 리포트"
    type=agent:    /addcmd auto_trading portfolio "GET /portfolio" "포트폴리오 조회"
    """
    config = _get_config(context)
    # context.args는 공백 기준 분리라 따옴표 그룹핑이 안 됨 → raw text에서 직접 파싱
    raw = update.message.text or ""
    # /addcmd 이후 부분
    parts = raw.split(None, 4)  # ['/addcmd', project, name, run_or_path, description?]
    if len(parts) < 4:
        await update.message.reply_text(
            "사용법:\n"
            "`/addcmd <프로젝트> <명령명> <실행어> [설명]`\n"
            "예) `/addcmd public_api report python report.py 월간리포트`\n"
            "예) `/addcmd auto_trading portfolio GET /portfolio 포트폴리오`",
            parse_mode="Markdown",
        )
        return

    _, project_name, cmd_name, run_or_path = parts[:4]
    description = parts[4].strip('"\'') if len(parts) == 5 else ""

    if project_name not in config.projects:
        await update.message.reply_text(f"❌ 프로젝트 '{project_name}'을 찾을 수 없습니다.")
        return

    try:
        spec = load_project_spec(config.projects[project_name])
    except FileNotFoundError as e:
        await update.message.reply_text(f"❌ {e}")
        return

    if spec.type == "command":
        spec.commands[cmd_name] = CommandSpec(run=run_or_path, description=description)
    else:
        # "GET /status" 또는 "POST /begin" 형태
        method_path = run_or_path.split(None, 1)
        if len(method_path) < 2:
            await update.message.reply_text("agent 명령 형식: `METHOD /path` (예: `GET /status`)", parse_mode="Markdown")
            return
        method, path = method_path
        spec.commands[cmd_name] = CommandSpec(method=method.upper(), path=path, description=description)

    save_project_spec(config.projects[project_name], spec)

    # 텔레그램 봇 커맨드 메뉴 갱신
    await _refresh_bot_commands(update, context, config)

    await update.message.reply_text(f"✅ `{project_name}` 에 명령 `/{cmd_name}` 추가됨", parse_mode="Markdown")


async def cmd_delcmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = _get_config(context)
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("사용법: /delcmd <프로젝트명> <명령명>")
        return

    project_name, cmd_name = args[0], args[1]

    if project_name not in config.projects:
        await update.message.reply_text(f"❌ 프로젝트 '{project_name}'을 찾을 수 없습니다.")
        return

    try:
        spec = load_project_spec(config.projects[project_name])
    except FileNotFoundError as e:
        await update.message.reply_text(f"❌ {e}")
        return

    if cmd_name not in spec.commands:
        await update.message.reply_text(f"❌ 명령 '{cmd_name}'이 존재하지 않습니다.")
        return

    del spec.commands[cmd_name]
    save_project_spec(config.projects[project_name], spec)

    await _refresh_bot_commands(update, context, config)
    await update.message.reply_text(f"✅ `{project_name}` 에서 명령 `/{cmd_name}` 삭제됨", parse_mode="Markdown")


async def _refresh_bot_commands(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    config: GlobalConfig,
) -> None:
    """등록된 모든 프로젝트의 명령을 취합해 텔레그램 봇 커맨드 메뉴를 갱신"""
    from telegram import BotCommand

    system_commands = [
        BotCommand("list", "등록된 프로젝트 목록"),
        BotCommand("select", "프로젝트 선택"),
        BotCommand("deselect", "프로젝트 선택 해제"),
        BotCommand("proj", "특정 프로젝트 명령 직접 실행"),
        BotCommand("register", "새 프로젝트 등록"),
        BotCommand("unregister", "프로젝트 등록 해제"),
        BotCommand("cmds", "프로젝트 명령 목록"),
        BotCommand("addcmd", "명령 추가"),
        BotCommand("delcmd", "명령 삭제"),
        BotCommand("help", "도움말"),
    ]

    project_commands = []
    for name, path in config.projects.items():
        try:
            spec = load_project_spec(path)
            for cmd_name, cmd in spec.commands.items():
                desc = cmd.description or f"{name}: {cmd_name}"
                project_commands.append(BotCommand(cmd_name, desc[:256]))
        except FileNotFoundError:
            pass

    # 시스템 명령 + 프로젝트 명령 (중복 제거, 최대 100개)
    seen: set[str] = set()
    all_commands = []
    for bc in system_commands + project_commands:
        if bc.command not in seen:
            seen.add(bc.command)
            all_commands.append(bc)
        if len(all_commands) >= 100:
            break

    await context.bot.set_my_commands(all_commands)
