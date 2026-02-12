"""
后台任务管理 - Swarm 运行控制
"""
import logging
import threading

logger = logging.getLogger(__name__)

_run_lock = threading.Lock()
_is_running = False


def is_swarm_running() -> bool:
    return _is_running


def run_swarm_in_background(fred_api_key: str | None = None, output_dir: str | None = None):
    """在后台线程执行一次 Swarm 运行"""
    global _is_running

    if not _run_lock.acquire(blocking=False):
        logger.warning("[Background] Swarm 已在运行中，跳过")
        return

    try:
        _is_running = True
        logger.info("[Background] 后台 Swarm 运行启动")

        from scheduler import run_update
        success = run_update(fred_api_key=fred_api_key, output_dir=output_dir)

        if success:
            logger.info("[Background] 后台 Swarm 运行完成")
        else:
            logger.warning("[Background] 后台 Swarm 运行失败")
    except Exception as e:
        logger.error(f"[Background] 后台 Swarm 异常: {e}")
    finally:
        _is_running = False
        _run_lock.release()
