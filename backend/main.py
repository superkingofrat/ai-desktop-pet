"""AI Assistant Backend — FastAPI + WebSocket server with conversation persistence."""

from __future__ import annotations

import json
import logging
import sys as _sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bus, _provider, _agent_loop, _db, _cm

    # ── Trigger auto-registration of BaseTool subclasses ──
    import agent.tools  # noqa: F401

    from bus.queue import MessageBus
    from providers.deepseek_provider import DeepSeekProvider
    from agent.loop import AgentLoop
    from db.database import Database
    from db.models import ConversationManager

    _db = Database()
    _cm = ConversationManager(_db)

    _bus = MessageBus()
    _provider = DeepSeekProvider()
    _agent_loop = AgentLoop(bus=_bus, provider=_provider)

    logger.info("Auto-registered tools: %s", _agent_loop.tools.tool_names)
    logger.info("AI Assistant backend started")
    yield
    logger.info("AI Assistant backend shutting down")
    _agent_loop = None
    _provider = None
    _bus = None
    _cm = None
    _db = None


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
    """WebSocket chat endpoint with streaming response.

    Query parameter ``session_id`` identifies the conversation.
    All messages are persisted via ``ConversationManager`` so that
    history and user profile survive across reconnects.
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

            # Honour the session_id sent in the first message body
            if data.get("session_id"):
                session_id = data["session_id"]

            logger.info("[WS] Received  session=%s  content=%.60s", session_id, content)

            # ── Special commands (no LLM) ──────────────────────────
            if content == "/new":
                continue  # simply ignore; old history is still in DB

            if content == "/help":
                await websocket.send_text(json.dumps({
                    "type": "reply",
                    "content": "Commands:\n/help - Show help",
                }))
                continue

            # ── Normal flow: stream through the agent ──────────────
            collected_parts: list[str] = []
            personality = data.get("personality") or ""

            async for event in _agent_loop.process_message_stream(
                content,
                personality=personality,
                session_id=session_id,
                conversation_manager=_cm,
            ):
                if event["type"] == "thinking":
                    await websocket.send_text(json.dumps({
                        "type": "thinking",
                        "content": event["content"],
                    }))
                elif event["type"] == "delta":
                    collected_parts.append(event["content"])
                    await websocket.send_text(json.dumps({
                        "type": "delta",
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
