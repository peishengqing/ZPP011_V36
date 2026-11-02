# -*- coding: utf-8 -*-
"""
定时报表调度器

在应用运行时自动触发报表生成。
代理模式：不直接启动子进程，而是在主线程中调度执行。
"""

import sched
import time
import threading
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Optional, Callable

from core.config_manager import ConfigManager


class ScheduledReportScheduler:
    """定时报表调度器"""

    def __init__(self):
        self.config = ConfigManager()
        self.scheduler = sched.scheduler(time.time, time.sleep)
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """启动调度器（仅当配置启用时）"""
        if self._running:
            return

        schedule_config = self.config.get('scheduled_reports', {})
        if not schedule_config.get('enabled', False):
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        # 立即计算下次触发时间并调度
        self._schedule_next()

    def stop(self):
        """停止调度器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _run_loop(self):
        """调度器运行循环"""
        while self._running:
            try:
                # 检查配置是否启用
                schedule_config = self.config.get('scheduled_reports', {})
                if not schedule_config.get('enabled', False):
                    # 取消所有待处理事件
                    self.scheduler.cancel_all()
                    break

                # 执行调度任务
                self.scheduler.enter(0, 1, self._execute_task)
                time.sleep(60)  # 每分钟检查一次
            except Exception:
                time.sleep(10)

    def _schedule_next(self):
        """计算并安排下一次触发"""
        schedule_config = self.config.get('scheduled_reports', {})
        schedule_type = schedule_config.get('schedule_type', 'daily')
        schedule_time_str = schedule_config.get('schedule_time', '08:00')

        try:
            schedule_time = datetime.strptime(schedule_time_str, '%H:%M').time()
        except ValueError:
            return

        now = datetime.now()
        next_trigger = datetime.combine(now.date(), schedule_time)

        if next_trigger <= datetime.now():
            # 今天的时间已过，安排到明天/下个月
            if schedule_type == 'daily':
                next_trigger += timedelta(days=1)
            elif schedule_type == 'weekly':
                next_trigger += timedelta(weeks=1)
            elif schedule_type == 'monthly':
                # 简单处理：下个月同一天同一时间
                next_trigger = next_trigger.replace(day=1)
                # 查找下个月第一个工作日（简化：直接用下月1日）
                if now.month == 12:
                    next_trigger = next_trigger.replace(month=1, year=now.year + 1)
                else:
                    next_trigger = next_trigger.replace(month=now.month + 1)

        # 计算等待时间
        delta = next_trigger - datetime.now()
        seconds = delta.total_seconds()

        if seconds > 0:
            self.scheduler.enter(seconds, 1, self._execute_task)

    def _execute_task(self):
        """执行定时报表任务"""
        schedule_config = self.config.get('scheduled_reports', {})
        output_dir = schedule_config.get('output_dir', '')
        include_ppt = schedule_config.get('include_ppt', False)

        if not output_dir:
            # 使用默认输出目录（上次导出目录）
            output_dir = self.config.get('last_export_dir', '')

        if not output_dir:
            output_dir = Path.home() / "Documents" / "ZPP011_Reports"
            output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 导出 Excel 报告
            # 注意：这里需要调用现有的导出逻辑，但因为是 GUI 应用，
            # 需要在主线程中执行。所以我们发送一个信号或调用主窗口方法。
            # 由于调度器是独立对象，这里简化处理：记录日志并提示用户
            import logging
            logger = logging.getLogger("ScheduledReport")
            logger.info(f"定时报表任务触发：{datetime.now()}")
            # TODO: 实现实际的导出任务调用
            # 需要与主窗口通信或通过中央事件总线
        except Exception as e:
            import logging
            logging.error(f"定时报表任务失败：{e}")

        # 安排下一次
        self._schedule_next()

    def set_enabled(self, enabled: bool):
        """启用/禁用定时报表"""
        current = self.config.get('scheduled_reports', {})
        current['enabled'] = enabled
        self.config.set('scheduled_reports', current)

        if enabled:
            self.start()
        else:
            self.stop()

    def set_schedule(self, schedule_type: str, schedule_time: str):
        """设置调度类型和时间"""
        current = self.config.get('scheduled_reports', {})
        current['schedule_type'] = schedule_type
        current['schedule_time'] = schedule_time
        self.config.set('scheduled_reports', current)

    def set_output_dir(self, output_dir: str):
        """设置输出目录"""
        current = self.config.get('scheduled_reports', {})
        current['output_dir'] = output_dir
        self.config.set('scheduled_reports', current)
