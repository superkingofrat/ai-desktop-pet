# AI 桌面宠物助手

基于 FastAPI + WebSocket + PyQt5 的智能桌面宠物，支持待办事项管理、流式 AI 对话。

## 功能特点
- 🐱 桌面悬浮宠物，可拖拽、双击唤醒对话窗口
- 💬 WebSocket 实时流式对话
- ✅ 待办事项管理（增加、查看、删除），持久化到 SQLite
- 🔌 易扩展的工具注册机制（ReAct Agent）

## 技术栈
- **后端**: Python 3.14, FastAPI, WebSocket, SQLite
- **前端**: PyQt5（桌面宠物窗口）, HTML/JS（可选）
- **AI**: DeepSeek API, OpenAI SDK

## 快速开始

### 1. 克隆项目
```bash
git clone https://github.com/superkingofrat/ai-desktop-pet.git
cd ai-desktop-pet
```