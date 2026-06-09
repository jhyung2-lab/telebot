# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 언어 및 커뮤니케이션 규칙

- **기본 응답 언어**: 한국어
- **코드 주석**: 한국어로 작성
- **커밋 메시지**: 한국어로 작성
- **문서화**: 한국어로 작성
- **변수명/함수명**: 영어 (코드 표준 준수)

## 프로젝트 개요

여러 프로젝트를 텔레그램 하나로 통합 제어하는 허브 봇.
단일 Bot Token으로 모든 프로젝트를 라우팅하며, 새 프로젝트는 `.telebot.yml` 파일 추가만으로 연동된다.

## 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# .env 파일 설정 (또는 ~/.telebot/config.yml에서 환경변수 참조)
cp .env.example .env
# .env에 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 입력

# 봇 실행
python main.py
```

## 아키텍처

### 프로젝트 타입

| 타입 | 대상 | 동작 방식 |
|------|------|-----------|
| `type: command` | 일회성 스크립트 | subprocess 실행 후 stdout 전송 |
| `type: agent` | 장기 실행 프로세스 | HTTP 통신 (localhost:PORT) |

### 핵심 파일

- `main.py` — Application 빌드 및 핸들러 등록
- `telebot/registry.py` — `~/.telebot/config.yml`과 각 프로젝트 `.telebot.yml` 로딩/저장
- `telebot/router.py` — 명령 파싱 및 프로젝트 dispatch 핵심 로직
- `telebot/session.py` — 채팅별 선택된 프로젝트 컨텍스트 (메모리, 1시간 타임아웃)
- `telebot/executor/command.py` — asyncio subprocess 실행
- `telebot/executor/agent.py` — aiohttp HTTP 클라이언트
- `telebot/handlers/system.py` — 시스템 명령 (/list, /select, /register, /addcmd, /delcmd 등)
- `telebot/handlers/project.py` — /proj 및 컨텍스트 기반 /<cmd> 라우팅
- `sdk/agent_server.py` — type=agent 프로젝트에서 재사용하는 경량 asyncio HTTP 서버

### 전역 설정

`~/.telebot/config.yml` — Bot Token, Chat ID, 등록된 프로젝트 경로 목록

### 새 프로젝트 연동

1. 프로젝트 루트에 `.telebot.yml` 생성
2. 텔레그램에서 `/register /path/to/project` 실행

**type=command 예시:**
```yaml
name: my_project
description: "설명"
type: command
commands:
  run:
    description: "실행"
    run: python main.py
    timeout: 60
```

**type=agent 예시:**
```yaml
name: my_project
description: "설명"
type: agent
port: 18001
commands:
  status:
    method: GET
    path: /status
```

type=agent 프로젝트는 `sdk/agent_server.py`의 `AgentServer`를 사용해 HTTP 서버를 내장한다.

## 텔레그램 명령 UX

```
/list                          등록된 프로젝트 목록
/select <이름>                 프로젝트 선택 (이후 /<cmd>가 자동 라우팅됨)
/deselect                      선택 해제
/proj <프로젝트> <명령>        직접 실행 (컨텍스트 불필요)
/register <경로>               새 프로젝트 등록
/unregister <이름>             프로젝트 등록 해제
/cmds [프로젝트]               명령 목록 조회
/addcmd <프로젝트> <명령> <실행어> [설명]   명령 추가 (재시작 없이 즉시 적용)
/delcmd <프로젝트> <명령>      명령 삭제
/help                          전체 명령 도움말
```
