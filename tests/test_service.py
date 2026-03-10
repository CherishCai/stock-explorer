"""服务层测试"""

import sys
from pathlib import Path

# 设置项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# 系统导入

import pytest

# 项目导入
from stock_explorer.service.manager import ServiceConfig, ServiceManager, ServiceStatus
from stock_explorer.service.scheduler import TaskScheduler, TaskStatus, TaskType


class TestServiceManager:
    @pytest.fixture
    def config(self):
        return ServiceConfig(
            scan_interval_hs300=1,
            scan_interval_market=1,
            scan_interval_industry=1,
            enable_hs300_scan=False,
            enable_market_scan=False,
            enable_industry_scan=False,
        )

    @pytest.fixture
    def manager(self, config):
        return ServiceManager(config)

    def test_manager_initialization(self, manager):
        assert manager is not None
        assert manager.status == ServiceStatus.STOPPED

    def test_manager_get_status(self, manager):
        status = manager.get_status()
        assert "status" in status
        assert status["status"] == "stopped"


class TestTaskScheduler:
    @pytest.fixture
    def scheduler(self):
        return TaskScheduler()

    def test_scheduler_initialization(self, scheduler):
        assert scheduler is not None
        assert len(scheduler.list_tasks()) == 0

    def test_add_interval_task(self, scheduler):
        def dummy_func():
            return "done"

        task = scheduler.add_interval_task("test_task", dummy_func, 1)
        assert task.name == "test_task"
        assert task.task_type == TaskType.INTERVAL

    def test_add_cron_task(self, scheduler):
        def dummy_func():
            return "done"

        task = scheduler.add_cron_task("cron_task", dummy_func, "0 9 * * *")
        assert task.name == "cron_task"
        assert task.task_type == TaskType.CRON

    def test_add_once_task(self, scheduler):
        def dummy_func():
            return "done"

        task = scheduler.add_once_task("once_task", dummy_func)
        assert task.name == "once_task"
        assert task.task_type == TaskType.ONCE

    def test_remove_task(self, scheduler):
        def dummy_func():
            return "done"

        scheduler.add_interval_task("test_task", dummy_func, 1)
        result = scheduler.remove_task("test_task")
        assert result is True

    def test_remove_nonexistent_task(self, scheduler):
        result = scheduler.remove_task("nonexistent")
        assert result is False

    def test_list_tasks(self, scheduler):
        def dummy_func():
            return "done"

        scheduler.add_interval_task("task1", dummy_func, 1)
        scheduler.add_interval_task("task2", dummy_func, 2)

        tasks = scheduler.list_tasks()
        assert len(tasks) == 2

    def test_get_task(self, scheduler):
        def dummy_func():
            return "done"

        added_task = scheduler.add_interval_task("test_task", dummy_func, 1)
        retrieved_task = scheduler.get_task("test_task")

        assert retrieved_task is not None
        assert retrieved_task.name == added_task.name


class TestServiceStatus:
    def test_service_status_values(self):
        assert ServiceStatus.STOPPED.value == "stopped"
        assert ServiceStatus.STARTING.value == "starting"
        assert ServiceStatus.RUNNING.value == "running"
        assert ServiceStatus.STOPPING.value == "stopping"
        assert ServiceStatus.ERROR.value == "error"


class TestTaskType:
    def test_task_type_values(self):
        assert TaskType.ONCE.value == "once"
        assert TaskType.INTERVAL.value == "interval"
        assert TaskType.CRON.value == "cron"


class TestTaskStatus:
    def test_task_status_values(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"
