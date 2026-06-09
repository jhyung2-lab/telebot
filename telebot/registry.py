"""
프로젝트 레지스트리: ~/.telebot/config.yml과 각 프로젝트의 .telebot.yml을 로딩/관리
"""
import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator


CONFIG_PATH = Path.home() / ".telebot" / "config.yml"


class CommandSpec(BaseModel):
    description: str = ""
    # type=command 필드
    run: str = ""
    timeout: int = 60
    # type=agent 필드
    method: str = "GET"
    path: str = ""


class ProjectSpec(BaseModel):
    name: str
    description: str = ""
    type: str = "command"  # "command" | "agent"
    port: int = 0           # type=agent 전용
    commands: dict[str, CommandSpec] = {}

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("command", "agent"):
            raise ValueError("type은 'command' 또는 'agent' 이어야 합니다")
        return v


class GlobalConfig(BaseModel):
    bot_token: str
    chat_id: str
    projects: dict[str, Path] = {}


def _resolve_env(value: str) -> str:
    """${VAR} 형태의 환경변수 참조를 실제 값으로 치환"""
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), value)


def load_global_config() -> GlobalConfig:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"전역 설정 파일이 없습니다: {CONFIG_PATH}")

    raw: dict[str, Any] = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    tg = raw.get("telegram", {})
    projects_raw = raw.get("projects", {}) or {}

    return GlobalConfig(
        bot_token=_resolve_env(tg.get("bot_token", "")),
        chat_id=_resolve_env(tg.get("chat_id", "")),
        projects={name: Path(info["path"]) for name, info in projects_raw.items()
                  if info.get("enabled", True)},
    )


def load_project_spec(project_path: Path) -> ProjectSpec:
    spec_file = project_path / ".telebot.yml"
    if not spec_file.exists():
        raise FileNotFoundError(f".telebot.yml 파일이 없습니다: {spec_file}")

    raw: dict[str, Any] = yaml.safe_load(spec_file.read_text()) or {}
    commands = {
        name: CommandSpec(**cmd) if isinstance(cmd, dict) else CommandSpec(run=str(cmd))
        for name, cmd in (raw.get("commands") or {}).items()
    }
    return ProjectSpec(
        name=raw.get("name", project_path.name),
        description=raw.get("description", ""),
        type=raw.get("type", "command"),
        port=raw.get("port", 0),
        commands=commands,
    )


def save_global_config(config: GlobalConfig) -> None:
    """수정된 전역 설정을 config.yml에 저장 (환경변수 참조 형태 유지)"""
    existing_raw: dict[str, Any] = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    projects_section: dict[str, Any] = {}
    for name, path in config.projects.items():
        projects_section[name] = {"path": str(path), "enabled": True}

    existing_raw["projects"] = projects_section
    CONFIG_PATH.write_text(yaml.dump(existing_raw, allow_unicode=True, default_flow_style=False))


def save_project_spec(project_path: Path, spec: ProjectSpec) -> None:
    """수정된 프로젝트 스펙을 .telebot.yml에 저장"""
    spec_file = project_path / ".telebot.yml"
    commands_raw: dict[str, Any] = {}
    for name, cmd in spec.commands.items():
        if spec.type == "command":
            commands_raw[name] = {"description": cmd.description, "run": cmd.run, "timeout": cmd.timeout}
        else:
            commands_raw[name] = {"description": cmd.description, "method": cmd.method, "path": cmd.path}

    data: dict[str, Any] = {
        "name": spec.name,
        "description": spec.description,
        "type": spec.type,
        "commands": commands_raw,
    }
    if spec.type == "agent":
        data["port"] = spec.port

    spec_file.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False))
