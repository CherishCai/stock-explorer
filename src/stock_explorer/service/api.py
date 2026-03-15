"""REST API 服务"""

import uvicorn
from fastapi import FastAPI, HTTPException, Query

from stock_explorer.data.storage import get_storage
from stock_explorer.logging.logger import get_logger
from stock_explorer.service.manager import ServiceManager, ServiceStatus
from stock_explorer.service.scheduler import TaskScheduler
from stock_explorer.signal.registry import SignalRegistry

logger = get_logger(__name__)


app = FastAPI(
    title="股票信号检测系统 API",
    description="A股市场实时信号检测与回测系统",
    version="1.0.0",
)


class APIConfig:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        reload: bool = False,
    ):
        self.host = host
        self.port = port
        self.reload = reload


service_manager: ServiceManager | None = None
task_scheduler: TaskScheduler | None = None


@app.on_event("startup")
async def startup_event():
    global service_manager, task_scheduler
    service_manager = ServiceManager()
    task_scheduler = TaskScheduler()
    logger.info("API 服务已启动")


@app.on_event("shutdown")
async def shutdown_event():
    if service_manager:
        service_manager.stop()
    if task_scheduler:
        task_scheduler.stop()
    logger.info("API 服务已关闭")


@app.get("/")
async def root():
    return {
        "name": "股票信号检测系统 API",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/api/service/status")
async def get_service_status():
    if service_manager is None:
        raise HTTPException(status_code=503, detail="服务管理器未初始化")
    return service_manager.get_status()


@app.post("/api/service/start")
async def start_service():
    if service_manager is None:
        raise HTTPException(status_code=503, detail="服务管理器未初始化")

    if service_manager.status == ServiceStatus.RUNNING:
        raise HTTPException(status_code=400, detail="服务已在运行")

    try:
        service_manager.start()
        return {"message": "服务启动成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务启动失败: {str(e)}") from e


@app.post("/api/service/stop")
async def stop_service():
    if service_manager is None:
        raise HTTPException(status_code=503, detail="服务管理器未初始化")

    try:
        service_manager.stop()
        return {"message": "服务停止成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务停止失败: {str(e)}") from e


@app.post("/api/service/restart")
async def restart_service():
    if service_manager is None:
        raise HTTPException(status_code=503, detail="服务管理器未初始化")

    try:
        service_manager.restart()
        return {"message": "服务重启成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务重启失败: {str(e)}") from e


@app.get("/api/signals")
async def get_signals(
    limit: int = Query(100, ge=1, le=1000),
    symbol: str | None = None,
    signal_type: str | None = None,
):
    storage = get_storage()
    try:
        # 使用存储实例的方法获取信号数据
        # 这里简化处理，实际应该根据storage的API来调整
        # 假设storage有一个get_signals方法
        signals = storage.get_signals(start_date="2000-01-01", end_date="2100-12-31")
        # 过滤和限制结果
        if symbol:
            signals = signals[signals["symbol"] == symbol]
        if signal_type:
            signals = signals[signals["signal_type"] == signal_type]
        signals = signals.head(limit)
        # 转换为字典列表
        results = signals.to_dict("records")
        return {"signals": results, "count": len(results)}
    finally:
        pass  # storage不需要手动关闭


@app.get("/api/signals/{signal_id}")
async def get_signal(signal_id: int):
    storage = get_storage()
    try:
        # 简化处理，实际应该根据storage的API来调整
        signals = storage.get_signals(start_date="2000-01-01", end_date="2100-12-31")
        signal = signals[signals["id"] == signal_id]
        if signal.empty:
            raise HTTPException(status_code=404, detail="信号不存在")
        return signal.to_dict("records")[0]
    finally:
        pass


@app.get("/api/watchlist")
async def get_watchlist():
    storage = get_storage()
    try:
        # 简化处理，实际应该根据storage的API来调整
        watchlist = storage.get_watchlist()
        return {"watchlist": watchlist, "count": len(watchlist)}
    finally:
        pass


@app.post("/api/watchlist")
async def add_to_watchlist(
    symbol: str = Query(...),
    notes: str | None = None,
):
    storage = get_storage()
    try:
        # 使用save_watchlist方法添加单个股票到关注列表
        storage.save_watchlist(
            [{"symbol": symbol, "name": notes, "category": "custom", "enabled": 1}]
        )
        return {"message": f"{symbol} 已添加到关注列表"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        pass


@app.delete("/api/watchlist/{symbol}")
async def remove_from_watchlist(symbol: str):
    storage = get_storage()
    try:
        # 直接执行SQL删除操作
        conn = storage._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watchlist WHERE symbol = ?", [symbol])
        conn.commit()
        storage._close_connection(conn)
        return {"message": f"{symbol} 已从关注列表移除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        pass


@app.get("/api/strategies")
async def list_strategies():
    registry = SignalRegistry()
    strategies = []
    for name in registry.list_detectors():
        detector = registry.get_detector(name)
        strategies.append(
            {
                "name": name,
                "description": getattr(detector, "__doc__", "") or "",
            }
        )
    return {"strategies": strategies}


@app.get("/api/scheduler/tasks")
async def get_scheduler_tasks():
    if task_scheduler is None:
        raise HTTPException(status_code=503, detail="任务调度器未初始化")

    tasks = []
    for task in task_scheduler.list_tasks():
        tasks.append(
            {
                "name": task.name,
                "type": task.task_type.value,
                "status": task.status.value,
                "interval": task.interval,
                "next_run": task.next_run.isoformat() if task.next_run else None,
                "last_run": task.last_run.isoformat() if task.last_run else None,
                "last_error": task.last_error,
            }
        )
    return {"tasks": tasks}


def run_api_server(config: APIConfig | None = None):
    config = config or APIConfig()
    logger.info(f"启动 API 服务器: {config.host}:{config.port}")
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        reload=config.reload,
    )
