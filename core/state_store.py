# core/state_store.py
import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Callable, Optional
from dataclasses import dataclass, field

# 状态类别白名单
STATE_CATEGORIES = ("filters", "sort", "ui", "data")


@dataclass
class AppState:
    """全局状态仓库：订阅/通知、持久化、防抖自动保存"""
    filters: Dict[str, Any] = field(default_factory=dict)
    sort: Dict[str, Any] = field(default_factory=dict)
    ui: Dict[str, Any] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)

    _listeners: Dict[str, List[Callable]] = field(default_factory=dict, init=False, repr=False)
    _persist_path: Optional[Path] = field(default=None, init=False, repr=False)
    _auto_save_timer: Optional[threading.Timer] = field(default=None, init=False, repr=False)
    _auto_save_delay: float = field(default=1.0, init=False)

    def subscribe(self, event: str, callback: Callable):
        self._listeners.setdefault(event, []).append(callback)

    def notify(self, event: str, **kwargs):
        for cb in self._listeners.get(event, []):
            try:
                cb(**kwargs)
            except Exception as e:
                from core.logger import get_logger
                get_logger("StateStore").error(f"通知回调失败 {event}: {e}")

    def _validate_category(self, category: str):
        if category not in STATE_CATEGORIES:
            raise ValueError(f"无效类别: {category}，必须是 {STATE_CATEGORIES}")

    def set(self, category: str, key: str, value: Any, persist: bool = False, auto_save: bool = False):
        self._validate_category(category)
        getattr(self, category)[key] = value
        self.notify(f"{category}.changed", key=key, value=value)
        self.notify(f"{category}.{key}.changed", value=value)
        if persist:
            self.save()
        if auto_save:
            self._schedule_auto_save()

    def get(self, category: str, key: str, default=None):
        self._validate_category(category)
        return getattr(self, category).get(key, default)

    def delete(self, category: str, key: str, persist: bool = False, auto_save: bool = False):
        self._validate_category(category)
        if key in getattr(self, category):
            del getattr(self, category)[key]
            self.notify(f"{category}.deleted", key=key)
        if persist:
            self.save()
        if auto_save:
            self._schedule_auto_save()

    def save(self, path: Path = None):
        if path is None:
            if self._persist_path is None:
                self._persist_path = Path.home() / ".zpp011_audit" / "state.json"
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            path = self._persist_path
        data = {
            "filters": self.filters,
            "sort": self.sort,
            "ui": self.ui,
            "data": self.data
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            from core.logger import get_logger
            get_logger("StateStore").debug(f"状态已保存到 {path}")
        except Exception as e:
            from core.logger import get_logger
            get_logger("StateStore").error(f"保存状态失败: {e}")

    def load(self, path: Path = None):
        if path is None:
            if self._persist_path is None:
                self._persist_path = Path.home() / ".zpp011_audit" / "state.json"
            path = self._persist_path
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.filters.clear()
            self.filters.update(data.get("filters", {}))
            self.sort.clear()
            self.sort.update(data.get("sort", {}))
            self.ui.clear()
            self.ui.update(data.get("ui", {}))
            self.data.clear()
            self.data.update(data.get("data", {}))
            self.notify("state.loaded")
            from core.logger import get_logger
            get_logger("StateStore").debug("状态加载完成")
        except Exception as e:
            from core.logger import get_logger
            get_logger("StateStore").error(f"加载状态失败: {e}")

    def set_persist_path(self, path: Path):
        """外部设置持久化路径（供 I2 配置管理器调用）"""
        self._persist_path = path

    def _schedule_auto_save(self):
        """防抖：延迟 N 秒后保存，期间多次触发只执行一次"""
        if self._auto_save_timer:
            self._auto_save_timer.cancel()
        self._auto_save_timer = threading.Timer(self._auto_save_delay, self.save)
        self._auto_save_timer.daemon = True
        self._auto_save_timer.start()

    def set_auto_save_delay(self, delay: float):
        self._auto_save_delay = delay


# 全局实例管理（显式初始化）
_state_instance = None


def init_state(persist_path: Path = None, auto_save_delay: float = 1.0) -> AppState:
    """应用启动时初始化，全局只调用一次"""
    global _state_instance
    _state_instance = AppState()
    if persist_path:
        _state_instance.set_persist_path(persist_path)
    _state_instance.set_auto_save_delay(auto_save_delay)
    _state_instance.load()
    return _state_instance


def get_state() -> AppState:
    """获取全局实例（必须先 init_state）"""
    if _state_instance is None:
        raise RuntimeError("StateStore 未初始化，请先调用 init_state()")
    return _state_instance
