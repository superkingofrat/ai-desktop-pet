import os, py_compile

path = "E:/ai-assistant/backend/main.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add include_router and scheduler import after existing imports
old = """from bus.queue import MessageBus
from providers.deepseek_provider import DeepSeekProvider
from agent.loop import AgentLoop
from db.database import Database"""
new = """from bus.queue import MessageBus
from providers.deepseek_provider import DeepSeekProvider
from agent.loop import AgentLoop
from db.database import Database
from scheduler import start_scheduler, shutdown_scheduler
from backend.api.routes import router as api_router"""

content = content.replace(old, new, 1)

# 2. Add app.include_router after app creation
old = """app = FastAPI(lifespan=lifespan)"""
new = """app = FastAPI(lifespan=lifespan)
app.include_router(api_router)"""

content = content.replace(old, new, 1)

# 3. Add start_scheduler() in lifespan after existing setup
old = """    logger.info("Backend ready")

    yield"""
new = """    start_scheduler()
    logger.info("Backend ready")

    yield
    shutdown_scheduler()"""

content = content.replace(old, new, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

py_compile.compile(path, doraise=True)
print("main.py updated OK")
