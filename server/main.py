"""
FastAPI 应用入口
- 挂载 API 路由
- CORS 配置
- 生产模式下服务前端静态文件
"""
import os
import sys
import logging

# 确保能 import 上层目录的模块
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.api import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)

app = FastAPI(
    title="Macro Factor Monitor API",
    description="美股宏观因子监控 - Agent Swarm REST API",
    version="3.0",
)

# CORS: 允许前端开发服务器访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",   # Docker frontend
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载 API 路由
app.include_router(router)

# 生产模式: 如果 frontend/dist 存在，则服务静态文件
_frontend_dist = os.path.join(_parent_dir, "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
    logging.getLogger(__name__).info(f"[Server] 挂载前端静态文件: {_frontend_dist}")
