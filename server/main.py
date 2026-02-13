"""
FastAPI 应用入口
- 挂载 API 路由
- CORS 配置
- 启动时自动回填历史数据
- 生产模式下服务前端静态文件
"""
import os
import sys
import logging
import threading

# 确保能 import 上层目录的模块
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.api import router
from server.deps import get_db, get_fred_api_key

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)

_logger = logging.getLogger(__name__)


def _run_backfill_if_needed():
    """后台检查并执行历史数据回填"""
    try:
        from backfill import needs_backfill, run_backfill
        db = get_db()
        if needs_backfill(db):
            fred_key = get_fred_api_key()
            _logger.info("[Startup] 检测到历史数据不足，开始后台回填...")
            count = run_backfill(db, fred_api_key=fred_key, days=90)
            _logger.info(f"[Startup] 历史数据回填完成，共插入 {count} 条记录")
        else:
            _logger.info("[Startup] 历史数据充足，跳过回填")
    except Exception as e:
        _logger.error(f"[Startup] 历史数据回填失败: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时触发历史数据回填"""
    thread = threading.Thread(target=_run_backfill_if_needed, daemon=True)
    thread.start()
    yield


app = FastAPI(
    title="Macro Factor Monitor API",
    description="美股宏观因子监控 - Agent Swarm REST API",
    version="3.0",
    lifespan=lifespan,
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
    _logger.info(f"[Server] 挂载前端静态文件: {_frontend_dist}")
