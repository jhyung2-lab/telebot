"""
사용자 세션: 채팅별로 현재 선택된 프로젝트를 메모리에 보관
"""
import time

SESSION_TIMEOUT = 3600  # 1시간 미사용 시 컨텍스트 초기화

_sessions: dict[int, dict] = {}


def get_project(chat_id: int) -> str | None:
    """현재 선택된 프로젝트명 반환. 타임아웃 초과 시 None."""
    session = _sessions.get(chat_id)
    if not session:
        return None
    if time.time() - session["last_active"] > SESSION_TIMEOUT:
        del _sessions[chat_id]
        return None
    return session["project"]


def set_project(chat_id: int, project_name: str) -> None:
    _sessions[chat_id] = {"project": project_name, "last_active": time.time()}


def clear_project(chat_id: int) -> None:
    _sessions.pop(chat_id, None)


def touch(chat_id: int) -> None:
    """마지막 활동 시각 갱신 (타임아웃 연장)"""
    if chat_id in _sessions:
        _sessions[chat_id]["last_active"] = time.time()
