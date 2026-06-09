"""
aiohttp 웹 서버: 대시보드 UI, REST API, WebSocket 실시간 스트리밍
"""
import json
import logging
from pathlib import Path

from aiohttp import web, WSMsgType

from telebot.monitor import Monitor

logger = logging.getLogger(__name__)

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>telebot 모니터</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1117; color: #e2e8f0; height: 100vh; display: flex; flex-direction: column; }

  /* 헤더 */
  header { background: #1a1d2e; border-bottom: 1px solid #2d3148; padding: 12px 20px; display: flex; align-items: center; gap: 16px; flex-shrink: 0; }
  header h1 { font-size: 16px; font-weight: 600; color: #7c8cf8; }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #4ade80; box-shadow: 0 0 6px #4ade80; animation: pulse 2s infinite; }
  .status-dot.offline { background: #f87171; box-shadow: 0 0 6px #f87171; animation: none; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
  .header-filters { display: flex; gap: 8px; margin-left: auto; align-items: center; }
  select, button { background: #2d3148; border: 1px solid #3d4168; color: #e2e8f0; padding: 5px 10px; border-radius: 6px; font-size: 13px; cursor: pointer; }
  select:focus, button:focus { outline: 2px solid #7c8cf8; }
  button:hover { background: #3d4168; }
  #btn-download { color: #7c8cf8; }
  #btn-clear { color: #f87171; }

  /* 레이아웃 */
  .main { display: flex; flex: 1; overflow: hidden; }

  /* 피드 */
  #feed { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 10px; }
  #feed::-webkit-scrollbar { width: 6px; }
  #feed::-webkit-scrollbar-track { background: transparent; }
  #feed::-webkit-scrollbar-thumb { background: #2d3148; border-radius: 3px; }

  .event { display: flex; flex-direction: column; gap: 4px; max-width: 85%; animation: fadeIn .2s ease; }
  @keyframes fadeIn { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:translateY(0)} }
  .event.in { align-self: flex-end; }
  .event.out { align-self: flex-start; }

  .event-meta { font-size: 11px; color: #64748b; display: flex; gap: 8px; align-items: center; }
  .event.in .event-meta { justify-content: flex-end; }

  .tag { background: #2d3148; padding: 2px 6px; border-radius: 4px; font-size: 10px; }
  .tag.project { color: #7c8cf8; }
  .tag.cmd { color: #34d399; }
  .tag.dur { color: #fbbf24; }
  .tag.err { color: #f87171; background: #2d1a1a; }

  .bubble { padding: 10px 14px; border-radius: 12px; font-size: 13px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
  .event.in .bubble { background: #2d3581; border-bottom-right-radius: 3px; }
  .event.out .bubble { background: #1e2433; border: 1px solid #2d3148; border-bottom-left-radius: 3px; }
  .event.out.has-error .bubble { border-color: #f87171; }

  .cmd-run { font-family: 'Courier New', monospace; font-size: 11px; color: #94a3b8; background: #111827; padding: 4px 8px; border-radius: 4px; margin-bottom: 6px; border-left: 2px solid #7c8cf8; }

  /* 사이드바 */
  #sidebar { width: 220px; background: #1a1d2e; border-left: 1px solid #2d3148; padding: 16px; overflow-y: auto; flex-shrink: 0; }
  #sidebar h2 { font-size: 13px; color: #64748b; margin-bottom: 12px; text-transform: uppercase; letter-spacing: .5px; }
  .stat-block { margin-bottom: 20px; }
  .stat-row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #2d3148; font-size: 13px; }
  .stat-row:last-child { border-bottom: none; }
  .stat-val { font-weight: 600; }
  .stat-val.ok { color: #4ade80; }
  .stat-val.err { color: #f87171; }
  .stat-val.accent { color: #7c8cf8; }

  #empty-msg { color: #64748b; text-align: center; margin-top: 40px; font-size: 14px; }
</style>
</head>
<body>
<header>
  <div class="status-dot" id="dot"></div>
  <h1>telebot 모니터</h1>
  <div class="header-filters">
    <select id="filter-project"><option value="">전체 프로젝트</option></select>
    <button id="btn-download">↓ 로그</button>
    <button id="btn-clear">✕ 지우기</button>
  </div>
</header>
<div class="main">
  <div id="feed"><div id="empty-msg">텔레그램으로 명령을 보내면 여기에 표시됩니다.</div></div>
  <div id="sidebar">
    <h2>통계</h2>
    <div class="stat-block">
      <div class="stat-row"><span>총 명령</span><span class="stat-val accent" id="s-total">0</span></div>
      <div class="stat-row"><span>오류</span><span class="stat-val err" id="s-err">0</span></div>
      <div class="stat-row"><span>평균 응답</span><span class="stat-val" id="s-avg">-</span></div>
    </div>
    <h2>프로젝트별</h2>
    <div class="stat-block" id="s-projects"></div>
  </div>
</div>

<script>
const feed = document.getElementById('feed');
const dot = document.getElementById('dot');
const filterProject = document.getElementById('filter-project');
let allEvents = [];
let stats = { total: 0, errors: 0, durations: [], projects: {} };

function fmt(ts) {
  const d = new Date(ts);
  return d.toLocaleTimeString('ko-KR', { hour12: false });
}

function escHtml(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function renderEvent(ev) {
  const wrap = document.createElement('div');
  wrap.className = `event ${ev.direction}` + (ev.error ? ' has-error' : '');
  wrap.dataset.id = ev.id;
  wrap.dataset.project = ev.project || '';

  const meta = document.createElement('div');
  meta.className = 'event-meta';

  const time = `<span>${fmt(ev.ts)}</span>`;
  const who = ev.direction === 'in'
    ? '<span style="color:#7c8cf8">사용자</span>'
    : '<span style="color:#94a3b8">봇</span>';

  let tags = '';
  if (ev.project) tags += `<span class="tag project">${escHtml(ev.project)}</span>`;
  if (ev.command) tags += `<span class="tag cmd">/${escHtml(ev.command)}</span>`;
  if (ev.duration_ms != null) tags += `<span class="tag dur">${(ev.duration_ms/1000).toFixed(1)}s</span>`;
  if (ev.error) tags += `<span class="tag err">오류</span>`;

  meta.innerHTML = ev.direction === 'in'
    ? `${tags}${who}${time}`
    : `${time}${who}${tags}`;

  const bubble = document.createElement('div');
  bubble.className = 'bubble';

  if (ev.direction === 'out' && ev.command_run) {
    const cmdLine = document.createElement('div');
    cmdLine.className = 'cmd-run';
    cmdLine.textContent = '$ ' + ev.command_run + (ev.project_path ? `  [${ev.project_path}]` : '');
    bubble.appendChild(cmdLine);
  }

  const content = document.createElement('span');
  const text = ev.direction === 'in' ? ev.text : (ev.result || ev.error || '');
  content.textContent = text;
  bubble.appendChild(content);

  wrap.appendChild(meta);
  wrap.appendChild(bubble);
  return wrap;
}

function applyFilter() {
  const proj = filterProject.value;
  document.querySelectorAll('.event').forEach(el => {
    el.style.display = (!proj || el.dataset.project === proj) ? '' : 'none';
  });
}

function addEvent(ev) {
  allEvents.push(ev);

  // 필터 옵션 갱신
  if (ev.project && !filterProject.querySelector(`option[value="${ev.project}"]`)) {
    const opt = document.createElement('option');
    opt.value = ev.project;
    opt.textContent = ev.project;
    filterProject.appendChild(opt);
  }

  // 통계 갱신
  if (ev.direction === 'out') {
    stats.total++;
    if (ev.error) stats.errors++;
    if (ev.duration_ms != null) stats.durations.push(ev.duration_ms);
    if (ev.project) stats.projects[ev.project] = (stats.projects[ev.project] || 0) + 1;
    updateStats();
  }

  const el = renderEvent(ev);
  const empty = document.getElementById('empty-msg');
  if (empty) empty.remove();
  feed.appendChild(el);
  applyFilter();
  feed.scrollTop = feed.scrollHeight;
}

function updateStats() {
  document.getElementById('s-total').textContent = stats.total;
  document.getElementById('s-err').textContent = stats.errors;
  const avg = stats.durations.length
    ? (stats.durations.reduce((a,b)=>a+b,0) / stats.durations.length / 1000).toFixed(1) + 's'
    : '-';
  document.getElementById('s-avg').textContent = avg;

  const container = document.getElementById('s-projects');
  container.innerHTML = '';
  Object.entries(stats.projects).sort((a,b)=>b[1]-a[1]).forEach(([name, cnt]) => {
    container.innerHTML += `<div class="stat-row"><span>${escHtml(name)}</span><span class="stat-val">${cnt}</span></div>`;
  });
}

// 기존 로그 로드
fetch('/api/logs').then(r => r.json()).then(data => {
  (data.events || []).forEach(addEvent);
});

// WebSocket 연결
function connect() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onopen = () => { dot.className = 'status-dot'; };
  ws.onclose = () => { dot.className = 'status-dot offline'; setTimeout(connect, 3000); };
  ws.onerror = () => ws.close();
  ws.onmessage = e => { try { addEvent(JSON.parse(e.data)); } catch {} };
}
connect();

// 필터
filterProject.addEventListener('change', applyFilter);

// 다운로드
document.getElementById('btn-download').addEventListener('click', () => {
  const blob = new Blob([allEvents.map(e=>JSON.stringify(e)).join('\n')], {type:'application/jsonl'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `telebot-${new Date().toISOString().slice(0,10)}.jsonl`;
  a.click();
});

// 지우기
document.getElementById('btn-clear').addEventListener('click', () => {
  feed.innerHTML = '';
  allEvents = [];
  stats = { total: 0, errors: 0, durations: [], projects: {} };
  updateStats();
  filterProject.length = 1;
});
</script>
</body>
</html>
"""


async def _handle_index(request: web.Request) -> web.Response:
    return web.Response(text=DASHBOARD_HTML, content_type="text/html", charset="utf-8")


async def _handle_logs(request: web.Request) -> web.Response:
    monitor: Monitor = request.app["monitor"]
    n = int(request.rel_url.query.get("n", 200))
    return web.Response(
        text=json.dumps({"events": monitor.recent(n)}, ensure_ascii=False),
        content_type="application/json",
        charset="utf-8",
    )


async def _handle_ws(request: web.Request) -> web.WebSocketResponse:
    monitor: Monitor = request.app["monitor"]
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    monitor.add_ws(ws)
    try:
        async for msg in ws:
            if msg.type == WSMsgType.ERROR:
                break
    finally:
        monitor.remove_ws(ws)
    return ws


async def start_web_server(monitor: Monitor, port: int = 8080) -> None:
    app = web.Application()
    app["monitor"] = monitor
    app.router.add_get("/", _handle_index)
    app.router.add_get("/api/logs", _handle_logs)
    app.router.add_get("/ws", _handle_ws)

    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    logger.info("대시보드: http://localhost:%d", port)
