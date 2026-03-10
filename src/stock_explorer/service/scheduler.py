"""任务调度器"""

import asyncio
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from stock_explorer.logging.logger import get_logger

logger = get_logger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(Enum):
    ONCE = "once"
    INTERVAL = "interval"
    CRON = "cron"


@dataclass
class Task:
    name: str
    func: Callable
    task_type: TaskType
    interval: int | None = None
    cron_expr: str | None = None
    next_run: datetime | None = None
    status: TaskStatus = TaskStatus.PENDING
    last_run: datetime | None = None
    last_result: Any | None = None
    last_error: str | None = None


class TaskScheduler:
    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._running = False
        self._lock = threading.Lock()

    def add_interval_task(
        self,
        name: str,
        func: Callable,
        interval_seconds: int,
    ) -> Task:
        with self._lock:
            task = Task(
                name=name,
                func=func,
                task_type=TaskType.INTERVAL,
                interval=interval_seconds,
                next_run=datetime.now(),
            )
            self._tasks[name] = task
            logger.info(f"添加定时任务: {name}, 间隔: {interval_seconds}秒")
            return task

    def add_cron_task(
        self,
        name: str,
        func: Callable,
        cron_expr: str,
    ) -> Task:
        with self._lock:
            task = Task(
                name=name,
                func=func,
                task_type=TaskType.CRON,
                cron_expr=cron_expr,
                next_run=self._parse_cron_next_run(cron_expr),
            )
            self._tasks[name] = task
            logger.info(f"添加Cron任务: {name}, 表达式: {cron_expr}")
            return task

    def add_once_task(
        self,
        name: str,
        func: Callable,
        run_at: datetime | None = None,
    ) -> Task:
        with self._lock:
            task = Task(
                name=name,
                func=func,
                task_type=TaskType.ONCE,
                next_run=run_at or datetime.now(),
            )
            self._tasks[name] = task
            logger.info(f"添加一次性任务: {name}")
            return task

    def remove_task(self, name: str) -> bool:
        with self._lock:
            if name in self._tasks:
                del self._tasks[name]
                logger.info(f"移除任务: {name}")
                return True
            return False

    def get_task(self, name: str) -> Task | None:
        return self._tasks.get(name)

    def list_tasks(self) -> list[Task]:
        return list(self._tasks.values())

    def _parse_cron_next_run(self, cron_expr: str) -> datetime:
        return datetime.now() + timedelta(minutes=1)

    def start(self):
        if self._running:
            logger.warning("调度器已在运行")
            return

        self._running = True
        logger.info("任务调度器已启动")

        thread = threading.Thread(target=self._run_loop, daemon=True)
        thread.start()

    def stop(self):
        self._running = False
        logger.info("任务调度器已停止")

    def _run_loop(self):
        while self._running:
            now = datetime.now()

            with self._lock:
                for task in self._tasks.values():
                    if task.next_run and now >= task.next_run:
                        self._execute_task(task)

            time.sleep(1)

    def _execute_task(self, task: Task):
        task.status = TaskStatus.RUNNING
        task.last_run = datetime.now()

        try:
            logger.debug(f"执行任务: {task.name}")
            result = task.func()
            task.last_result = result
            task.status = TaskStatus.COMPLETED
            task.last_error = None

        except Exception as e:
            logger.error(f"任务执行失败 {task.name}: {e}")
            task.status = TaskStatus.FAILED
            task.last_error = str(e)

        if task.task_type == TaskType.INTERVAL and task.interval:
            task.next_run = datetime.now() + timedelta(seconds=task.interval)
        elif task.task_type == TaskType.ONCE:
            task.next_run = None
            task.status = TaskStatus.COMPLETED
        else:
            task.next_run = datetime.now() + timedelta(minutes=1)


class AsyncTaskScheduler:
    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._running = False
        self._lock = asyncio.Lock()

    async def add_interval_task(
        self,
        name: str,
        func: Callable,
        interval_seconds: int,
    ) -> Task:
        async with self._lock:
            task = Task(
                name=name,
                func=func,
                task_type=TaskType.INTERVAL,
                interval=interval_seconds,
                next_run=datetime.now(),
            )
            self._tasks[name] = task
            logger.info(f"添加异步定时任务: {name}, 间隔: {interval_seconds}秒")
            return task

    async def start(self):
        self._running = True
        logger.info("异步任务调度器已启动")

        asyncio.create_task(self._run_loop())

    async def stop(self):
        self._running = False
        logger.info("异步任务调度器已停止")

    async def _run_loop(self):
        while self._running:
            now = datetime.now()

            async with self._lock:
                for task in self._tasks.values():
                    if task.next_run and now >= task.next_run:
                        asyncio.create_task(self._execute_task(task))

            await asyncio.sleep(1)

    async def _execute_task(self, task: Task):
        task.status = TaskStatus.RUNNING
        task.last_run = datetime.now()

        try:
            logger.debug(f"执行异步任务: {task.name}")
            if asyncio.iscoroutinefunction(task.func):
                result = await task.func()
            else:
                result = await asyncio.to_thread(task.func)
            task.last_result = result
            task.status = TaskStatus.COMPLETED

        except Exception as e:
            logger.error(f"异步任务执行失败 {task.name}: {e}")
            task.status = TaskStatus.FAILED
            task.last_error = str(e)

        if task.task_type == TaskType.INTERVAL and task.interval:
            task.next_run = datetime.now() + timedelta(seconds=task.interval)
