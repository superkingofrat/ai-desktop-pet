"""AI Assistant Backend - FastAPI + WebSocket + Agent Loop + Tool System"""

from __future__ import annotations

import json
import logging
import sys as _sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bus, _provider, _agent_loop

    from bus.queue import MessageBus
    from providers.deepseek_provider import DeepSeekProvider
    from agent.loop import AgentLoop
    from agent.tools.add_todo import AddTodoTool

    _bus = MessageBus()
    _provider = DeepSeekProvider()
    _agent_loop = AgentLoop(bus=_bus, provider=_provider)
    _agent_loop.tools.register(AddTodoTool())
    logger.info("Registered tools: %s", _agent_loop.tools.tool_names)
    logger.info("AI Assistant backend started")
    yield
    logger.info("AI Assistant backend shutting down")
    _agent_loop = None
    _provider = None
    _bus = None


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
async def ws_chat(websocket: WebSocket):
    """WebSocket chat endpoint with streaming response."""
    if _agent_loop is None:
        await websocket.close(code=1013, reason="Agent not initialized")
        return

    await websocket.accept()
    history: list[dict] = []
    logger.info("[WS] Connection established")

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            content = data.get("content", "").strip()
            if not content:
                continue

            logger.info("[WS] Received: %s", content[:60])

            if content == "/new":
                history.clear()
                await websocket.send_text(json.dumps({
                    "type": "reply", "content": "New session started.",
                }))
                continue

            if content == "/help":
                await websocket.send_text(json.dumps({
                    "type": "reply",
                    "content": "Commands:\n/new - New conversation\n/help - Show help",
                }))
                continue

            collected_parts: list[str] = []

            async for event in _agent_loop.process_message_stream(content, history=history):
                if event["type"] == "thinking":
                    await websocket.send_text(json.dumps({
                        "type": "thinking", "content": event["content"],
                    }))
                elif event["type"] == "delta":
                    collected_parts.append(event["content"])
                    await websocket.send_text(json.dumps({
                        "type": "delta", "content": event["content"],
                    }))
                elif event["type"] == "tool_call":
                    await websocket.send_text(json.dumps({
                        "type": "tool_call", "tool": event["tool"], "args": event["args"],
                    }))
                elif event["type"] == "tool_result":
                    await websocket.send_text(json.dumps({
                        "type": "tool_result", "tool": event["tool"], "result": event["result"],
                    }))
                elif event["type"] == "done":
                    final = event.get("content", "") or "".join(collected_parts)
                    await websocket.send_text(json.dumps({
                        "type": "done", "content": final,
                    }))
                    history.append({"role": "user", "content": content})
                    history.append({"role": "assistant", "content": final})
                    if len(history) > 40:
                        history = history[-40:]
                elif event["type"] == "error":
                    await websocket.send_text(json.dumps({
                        "type": "error", "content": event["content"],
                    }))

    except WebSocketDisconnect:
        logger.info("[WS] Connection closed")
    except Exception as e:
        logger.exception("[WS] Error: %s", e)
        try:
            await websocket.send_text(json.dumps({"type": "error", "content": f"Server error: {e}"}))
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
