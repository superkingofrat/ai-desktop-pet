"""AI Assistant Backend — FastAPI + WebSocket with streaming toggle + semantic cache."""

from __future__ import annotations

import json
import logging
import sys as _sys
from contextlib import asynccontextmanager
import asyncio

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from backend.core.config import settings
from perception import get_active_window_title, is_entertainment_app

FOCUS_THRESHOLD = 900  # 15 min

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=_sys.stdout,
    force=True,
)
logger = logging.getLogger("assistant")

_bus = None
_provider = None
_agent_loop = None
_db = None
_cm = None
_cache = None
_window_clients: set[WebSocket] = set()
_window_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bus, _provider, _agent_loop, _db, _cm, _cache

    import agent.tools  # noqa: F401

    from bus.queue import MessageBus
    from providers.deepseek_provider import DeepSeekProvider
    from agent.loop import AgentLoop
    from db.database import Database
    from db.models import ConversationManager
    from cache.semantic_cache import SemanticCache

    _db = Database(db_path=settings.db_path)
    _cm = ConversationManager(_db)
    _cache = SemanticCache(db_path=settings.cache_db_path)

    _bus = MessageBus()
    _provider = DeepSeekProvider()
    _agent_loop = AgentLoop(bus=_bus, provider=_provider)

    logger.info("Auto-registered tools: %s", _agent_loop.tools.tool_names)
    logger.info("AI Assistant backend started  (cache=%s)", _cache is not None)
    global _window_task
    _window_task = asyncio.create_task(_window_monitor_loop())
    yield
    _window_task.cancel()
    try:
        await _window_task
    except asyncio.CancelledError:
        pass
    logger.info("AI Assistant backend shutting down")
    _agent_loop = None
    _provider = None
    _bus = None
    _cm = None
    _db = None
    _cache = None


app = FastAPI(title="AI Assistant", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "tools": list(_agent_loop.tools.tool_names) if _agent_loop else [],
    }


@app.websocket("/ws/chat")
async def ws_chat(
    websocket: WebSocket,
    session_id: str = Query(default="default"),
):
    """WebSocket chat endpoint with configurable streaming.

    Client can set ``{"stream": true}`` in the message body to receive
    per-token updates (``token`` events).  Without it (default), the
    complete response is sent as a single ``reply`` event.
    """
    if _agent_loop is None or _cm is None:
        await websocket.close(code=1013, reason="Service not initialized")
        return

    await websocket.accept()
    logger.info("[WS] Connected  session=%s", session_id)

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            content = data.get("content", "").strip()
            if not content:
                continue

            if data.get("session_id"):
                session_id = data["session_id"]

            stream = data.get("stream", True)
            logger.info(
                "[WS] Received  session=%s  stream=%s  content=%.60s",
                session_id, stream, content,
            )

            if content == "/help":
                await websocket.send_text(json.dumps({
                    "type": "reply",
                    "content": "Commands:\n/help - Show help\n/clear - Clear cache",
                }))
                continue

            if content == "/clear" and _cache:
                _cache.clear()
                await websocket.send_text(json.dumps({
                    "type": "reply",
                    "content": "Cache cleared.",
                }))
                continue

            # ── Stream or batch ──────────────────────────────────
            personality = data.get("personality") or ""
            collected_parts: list[str] = []

            async for event in _agent_loop.process_message_stream(
                content,
                personality=personality,
                session_id=session_id,
                conversation_manager=_cm,
                semantic_cache=_cache,
            ):
                if stream:
                    # ── Streaming mode: send every chunk ─────
                    if event["type"] == "delta":
                        collected_parts.append(event["content"])
                        await websocket.send_text(json.dumps({
                            "type": "token",
                            "content": event["content"],
                        }))
                    elif event["type"] == "thinking":
                        await websocket.send_text(json.dumps({
                            "type": "thinking",
                            "content": event["content"],
                        }))
                    elif event["type"] == "tool_call":
                        await websocket.send_text(json.dumps({
                            "type": "tool_call",
                            "tool": event["tool"],
                            "args": event["args"],
                        }))
                    elif event["type"] == "tool_result":
                        await websocket.send_text(json.dumps({
                            "type": "tool_result",
                            "tool": event["tool"],
                            "result": event["result"],
                        }))
                    elif event["type"] == "done":
                        final = event.get("content", "") or "".join(collected_parts)
                        await websocket.send_text(json.dumps({
                            "type": "done",
                            "content": final,
                        }))
                    elif event["type"] == "error":
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "content": event["content"],
                        }))
                else:
                    # ── Batch mode: collect and send once ────
                    if event["type"] == "delta":
                        collected_parts.append(event["content"])
                    elif event["type"] == "thinking":
                        pass  # silent in batch mode
                    elif event["type"] == "tool_call":
                        # Notify but don't stream content
                        await websocket.send_text(json.dumps({
                            "type": "tool_call",
                            "tool": event["tool"],
                            "args": event["args"],
                        }))
                    elif event["type"] == "tool_result":
                        await websocket.send_text(json.dumps({
                            "type": "tool_result",
                            "tool": event["tool"],
                            "result": event["result"],
                        }))
                    elif event["type"] == "done":
                        final = event.get("content", "") or "".join(collected_parts)
                        await websocket.send_text(json.dumps({
                            "type": "reply",
                            "content": final,
                        }))
                    elif event["type"] == "error":
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "content": event["content"],
                        }))

    except WebSocketDisconnect:
        logger.info("[WS] Disconnected  session=%s", session_id)
    except Exception as e:
        logger.exception("[WS] Error  session=%s: %s", session_id, e)
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "content": f"Server error: {e}",
            }))
        except Exception:
            pass


async def _send_focus_reminder(title: str, duration: float):
    """Send focus-reminder via /ws/window with personalized tip."""
    minutes = int(duration / 60)
    tip = ""
    try:
        from db.database import Database, search_memories
        db = Database()
        prefs = search_memories(db, "")
        for p in prefs:
            if p.get("memory_type") == "preference":
                content = p.get("content", "")
                if any(kw in content for kw in ("工作", "学习", "专注")):
                    tip = f"\u4f60\u4e4b\u524d\u63d0\u5230 {content}\uff0c\u8981\u5207\u6362\u56de\u5de5\u4f5c\u5417\uff1f"
                    break
    except Exception:
        pass

    msg = __import__("json").dumps({
        "type": "focus_reminder",
        "app": title,
        "duration_minutes": minutes,
        "message": f"\u4f60\u5df2\u4f7f\u7528 {title} {minutes} \u5206\u949f\uff0c\u5efa\u8bae\u4f11\u606f\u4e00\u4e0b",
        "personalized_tip": tip,
    })

    dead = set()
    for ws in _window_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    _window_clients -= dead


async def send_alert(message: str):
    """Send an alert message to all connected /ws/window clients."""
    msg = __import__("json").dumps({"type": "alert", "content": message})
    dead = set()
    for ws in _window_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    _window_clients -= dead


async def _window_monitor_loop():
    """Background task: poll active window, track entertainment, send reminders."""
    last_title = None
    activity_start_time = None

    while True:
        await asyncio.sleep(5)
        try:
            title = get_active_window_title()
            now = time.time()

            if title and title != last_title:
                last_title = title
                activity_start_time = now
                msg = json.dumps({
                    "type": "window_change",
                    "title": title,
                })
                dead = set()
                for ws in _window_clients:
                    try:
                        await ws.send_text(msg)
                    except Exception:
                        dead.add(ws)
                _window_clients -= dead

            if title and activity_start_time is not None:
                if is_entertainment_app(title):
                    duration = now - activity_start_time
                    if duration > FOCUS_THRESHOLD:
                        await _send_focus_reminder(title, duration)
                        activity_start_time = now
        except Exception:
            pass


@app.websocket("/ws/window")
async def ws_window(websocket: WebSocket):
    """WebSocket endpoint for active-window change events."""
    await websocket.accept()
    _window_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _window_clients.discard(websocket)


@app.post("/focus-feedback")
async def focus_feedback(data: dict):
    """Store user feedback from focus-reminder dialog."""
    choice = data.get("choice", "")
    app_name = data.get("app", "")
    msg = f"\u7528\u6237\u9009\u62e9: {choice}"
    if app_name:
        msg += f" (\u5e94\u7528: {app_name})"
    try:
        from db.database import Database, add_memory
        add_memory(Database(), msg, "focus_feedback")
    except Exception:
        pass
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.host, port=settings.port, reload=False)
