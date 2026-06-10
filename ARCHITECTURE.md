# AI Assistant — 架构文档

## 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                   PyQt5 桌面客户端                        │
│                     (frontend/)                          │
│                                                          │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │ MainWindow │──▶│  ChatWidget  │──▶│  QWebSocket   │  │
│  └──────────┘    └──────────────┘    └───────┬───────┘  │
│                                               │          │
└───────────────────────────────────────────────┼──────────┘
                                                │
                                          WebSocket
                                          ws://127.0.0.1:8000/ws/chat
                                                │
┌───────────────────────────────────────────────┼──────────┐
│                  FastAPI 服务端                  │          │
│                    (backend/)                  │          │
│                                               ▼          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              WebSocket 端点 (/ws/chat)                │ │
│  │    ┌───────────┐   JSON 消息:                         │ │
│  │    │  lifespan  │   ◀── {content, personality}       │ │
│  │    │  启动/关闭  │   ──▶ {type, content/tool/...}    │ │
│  │    └─────┬─────┘                                     │ │
│  └──────────┼──────────────────────────────────────────┘ │
│             │                                            │
│             ▼                                            │
│  ┌─────────────────┐    ┌──────────────┐                 │
│  │   AgentLoop     │───▶│  ToolRegistry │               │
│  │   (agent/)      │    │  (agent/tools/)│               │
│  └────────┬────────┘    └──────────────┘                 │
│           │                                              │
│           ▼                                              │
│  ┌─────────────────┐    ┌──────────────┐                 │
│  │ DeepSeekProvider│───▶│   MessageBus  │                │
│  │  (providers/)   │    │    (bus/)     │                │
│  └─────────────────┘    └──────────────┘                 │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │  db/     │  │  config/ │  │  tools/  │               │
│  └──────────┘  └──────────┘  └──────────┘               │
└──────────────────────────────────────────────────────────┘
```

## WebSocket 通信流程

```
 PyQt5 客户端                      FastAPI 服务端
     │                               │
     │  ws://127.0.0.1:8000/ws/chat  │
     │──────────────────────────────>│  (连接建立)
     │                               │
     │  {"content": "你好"}          │
     │──────────────────────────────>│
     │                               │────▶ AgentLoop.process_message_stream()
     │  {"type":"thinking",...}      │◀────
     │<──────────────────────────────│
     │  {"type":"delta","content":...}│◀──── LLM 流式输出
     │<──────────────────────────────│
     │  {"type":"tool_call",...}     │◀──── 触发工具调用
     │<──────────────────────────────│
     │  {"type":"tool_result",...}   │◀──── 工具执行结果
     │<──────────────────────────────│
     │  {"type":"done","content":...}│◀──── 最终回复
     │<──────────────────────────────│
```

## 目录结构

```
ai-assistant/
│
├── backend/                        # FastAPI 后端服务
│   ├── __init__.py                 #   包标记
│   ├── main.py                     #   FastAPI 应用、生命周期、WebSocket 端点
│   ├── api/                        #   REST API 路由
│   │   ├── __init__.py
│   │   └── routes.py               #   健康检查、会话管理端点
│   ├── core/                       #   核心配置与依赖注入
│   │   ├── __init__.py
│   │   └── config.py               #   从 .env / 环境变量加载设置
│   └── services/                   #   业务逻辑编排
│       ├── __init__.py
│       └── chat_service.py         #   聊天消息路由服务
│
├── agent/                          # AI 代理核心
│   ├── __init__.py                 #
│   ├── loop.py                     #   主循环（流式输出 + 工具调用）
│   └── tools/                      #   工具系统（OpenAI 函数调用格式）
│       ├── __init__.py
│       ├── base.py                 #   BaseTool 抽象基类 + TOOL_REGISTRY
│       ├── registry.py             #   ToolRegistry 动态注册管理
│       ├── add_todo.py             #   待办事项工具 (TodoTool)
│       ├── calculator_tool.py      #   数学计算器 (CalculatorTool)
│       └── weather_tool.py         #   模拟天气查询 (WeatherTool)
│
├── bus/                            # 异步消息总线（解耦层）
│   ├── __init__.py
│   ├── events.py                   #   InboundMessage / OutboundMessage
│   └── queue.py                    #   异步队列（发布/订阅）
│
├── providers/                      # LLM 提供者抽象
│   ├── __init__.py
│   ├── base.py                     #   BaseProvider 抽象接口
│   └── deepseek_provider.py        #   DeepSeek（兼容 OpenAI）实现
│
├── tools/                          # 独立工具函数（非 agent 工具）
│   ├── __init__.py
│   └── helpers.py                  #   JSON 读写、时间戳等
│
├── db/                             # 数据持久化层
│   ├── __init__.py
│   ├── database.py                 #   数据库管理器（JSON / 后续 SQLite）
│   ├── models.py                   #   数据模型（Conversation, TodoItem）
│   └── repository.py               #   通用 CRUD 仓储
│
├── frontend/                       # PyQt5 桌面客户端
│   ├── __init__.py
│   ├── app.py                      #   QApplication 入口
│   ├── main_window.py              #   主窗口，QWebSocket 连接
│   ├── widgets/                    #   自定义可复用组件
│   │   ├── __init__.py
│   │   └── chat_widget.py          #   聊天显示 + 输入，支持流式渲染
│   └── resources/                  #   图标、样式表、图片
│
├── config/                         # 配置（从 backend.core 重新导出）
│   ├── __init__.py
│   └── settings.py                 #   重新导出的 Settings
│
├── scripts/                        # 一次性脚本
│   ├── __init__.py
│   └── ...
│
├── tests/                          # 测试套件
│   ├── __init__.py
│   ├── test_agent/
│   ├── test_backend/
│   └── ...
│
├── electron-pet/                   # （可选）Electron 桌面宠物
│
├── .env                            # 环境变量
├── .env.example                    # 环境变量模板
├── .gitignore
├── requirements.txt                # Python 依赖
├── README.md
└── ARCHITECTURE.md                 # 本文档
```

## 模块职责

| 模块         | 分层       | 职责                                           |
|-------------|-----------|------------------------------------------------|
| `backend/`  | 服务端      | FastAPI 应用、WebSocket 端点、REST API、DI 配置   |
| `agent/`    | 核心逻辑    | 代理循环、工具注册、消息处理                       |
| `providers/`| 集成层      | LLM API 抽象（DeepSeek、OpenAI 等）              |
| `bus/`      | 解耦层      | 通道与代理之间的异步消息队列                       |
| `tools/`    | 工具函数    | 独立辅助函数（文件 I/O、格式化）                   |
| `db/`       | 持久化      | 数据模型与仓储（待办、会话存储）                   |
| `frontend/` | 客户端      | PyQt5 图形界面、QWebSocket 客户端、聊天 UI         |
| `config/`   | 配置        | 从环境变量集中加载的设置                          |

## 关键设计决策

1. **WebSocket 作为通信骨架** — `frontend/` 中的 `QWebSocket` 客户端直接与 FastAPI WebSocket 端点通信，无需 HTTP 轮询。服务端以 JSON 帧流式推送 `thinking`、`delta`、`tool_call`、`tool_result`、`done` 等事件类型。

2. **Agent 循环负责编排** — `agent/loop.py` 中的 `AgentLoop` 管理多轮推理：用户消息 → LLM 流式输出 → 工具执行 → 最终回答。完全与传输层解耦。

3. **提供者抽象** — `providers/base.py` 定义接口，`deepseek_provider.py` 实现。更换为 OpenAI 或 Anthropic 只需新增一个提供者文件。

4. **消息总线解耦** — `bus/` 使得未来添加多通道（Telegram、Discord、CLI）时无需改动代理核心。

## 启动方式

```bash
# 后端（项目根目录下）
uvicorn backend.main:app --reload --port 8000

# 前端（另开终端）
python -m frontend.app
```

---
