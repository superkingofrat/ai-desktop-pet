AI 桌面宠物助手

基于 FastAPI + WebSocket + PyQt5 的智能桌面宠物，支持待办事项管理、流式 AI 对话。

功能特点

- 🐱 桌面悬浮宠物，可拖拽、双击唤醒对话窗口
- 💬 WebSocket 实时流式对话
- ✅ 待办事项管理（增加、查看、删除），持久化到 SQLite
- 🔌 易扩展的工具注册机制（ReAct Agent）

技术栈

- 后端: Python 3.14, FastAPI, WebSocket, SQLite
- 前端: PyQt5（桌面宠物窗口）, HTML/JS（可选）
- AI: DeepSeek API, OpenAI SDK

快速开始

1. 克隆项目

    git clone https://github.com/superkingofrat/ai-desktop-pet.git
    cd ai-desktop-pet

2. 安装依赖

bash

    pip install -r requirements.txt

3. 配置 API Key

创建 .env 文件（可从 .env.example 复制），填入你的 DeepSeek API Key：

text

    DEEPSEEK_API_KEY=sk-xxxxx

4. 启动后端

bash

    python main.py

5. 启动桌面宠物（新开终端）

bash

    python pet.py

双击右下角宠物图标即可对话。
