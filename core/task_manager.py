# -*- coding: utf-8 -*-
# core/task_manager.py
import threading
import queue
import uuid
from concurrent.futures import ThreadPoolExecutor


class TaskManager:
    def __init__(self, max_workers=2):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.callback_queue = queue.Queue()
        self._tasks = {}  # task_id -> {"future": future, "cancel_flag": threading.Event}
        self._polling = False

    def run(self, func, callback=None, error_callback=None, progress_callback=None):
        """
        异步执行任务
        :param func: 可调用对象，接受 (progress_callback, cancel_flag) 两个可选参数
        :param callback: 成功回调，接收 func 的返回值
        :param error_callback: 错误回调，接收异常对象
        :param progress_callback: 进度回调，由 TaskManager 传递给 func，func 内部调用它
        """
        task_id = str(uuid.uuid4())
        cancel_flag = threading.Event()
        future = self.executor.submit(
            self._run_task, task_id, func, cancel_flag, progress_callback
        )
        self._tasks[task_id] = {"future": future, "cancel_flag": cancel_flag}
        self._current_task_id = task_id
        future.add_done_callback(
            lambda f: self._on_task_done(task_id, f, callback, error_callback)
        )

    def _run_task(self, task_id, func, cancel_flag, progress_callback):
        """在线程中执行实际任务"""
        import inspect
        sig = inspect.signature(func)
        kwargs = {}
        if 'cancel_flag' in sig.parameters:
            kwargs['cancel_flag'] = cancel_flag
        if 'progress_callback' in sig.parameters:
            kwargs['progress_callback'] = progress_callback
        return func(**kwargs)

    def _on_task_done(self, task_id, future, callback, error_callback):
        """任务完成后的回调（在线程池线程中执行，需转发到主线程）"""
        try:
            result = future.result()
            self.callback_queue.put(("success", result, callback))
        except Exception as e:
            self.callback_queue.put(("error", e, error_callback))
        finally:
            self._tasks.pop(task_id, None)
            if getattr(self, "_current_task_id", None) == task_id:
                self._current_task_id = None

    def cancel(self, task_id):
        """取消指定任务（如果尚未开始或正在运行）"""
        task = self._tasks.get(task_id)
        if task:
            task["cancel_flag"].set()
            task["future"].cancel()

    @property
    def current_task_id(self):
        return getattr(self, '_current_task_id', None)

    def cancel_current(self):
        """取消当前运行中的任务"""
        tid = self.current_task_id
        if tid:
            self.cancel(tid)

    def cancel_all(self):
        """取消所有待执行/运行中的任务"""
        for task_id in list(self._tasks.keys()):
            self.cancel(task_id)

    def poll(self, master, interval=50):
        """轮询回调队列，将回调调度到主线程执行"""
        if not self._polling:
            self._polling = True
            self._poll(master, interval)

    def _poll(self, master, interval):
        try:
            typ, data, cb = self.callback_queue.get_nowait()
            if typ == "success" and cb:
                cb(data)
            elif typ == "error" and cb:
                cb(data)  # error_callback 接收异常对象
        except queue.Empty:
            pass
        finally:
            master.after(interval, self._poll, master, interval)
