# modules/audit/views/audit_view.py
"""
MVP View 接口定义。

Presenter 通过此接口与 UI 层交互，禁止 Presenter 直接操作 tkinter 控件。
events.py 中的 ZPP011Beautiful 类实现此接口（作为 ViewBridge）。
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
import pandas as pd


class AuditViewBridge(ABC):
    """View 层抽象接口 — Presenter 只调用这些方法"""

    # ==================== 数据访问 ====================

    @abstractmethod
    def get_audit_data(self) -> pd.DataFrame:
        """获取当前 Treeview 中的审核数据（完整 DataFrame）"""
        ...

    @abstractmethod
    def get_output_path(self) -> Optional[str]:
        """获取当前分析输出目录路径"""
        ...

    @abstractmethod
    def get_alt_pairs(self) -> list:
        """获取替代料配对列表"""
        ...

    @abstractmethod
    def get_input_file(self) -> Optional[str]:
        """获取当前输入文件路径"""
        ...

    # ==================== Treeview 操作 ====================

    @abstractmethod
    def set_tree_data(self, df: pd.DataFrame):
        """用新数据替换 Treeview 内容"""
        ...

    @abstractmethod
    def get_tree_selection(self) -> List[int]:
        """获取当前 Treeview 选中行的索引列表"""
        ...

    @abstractmethod
    def highlight_rows(self, indices: List[int], color: str = ''):
        """高亮指定行"""
        ...

    # ==================== 进度与日志 ====================

    @abstractmethod
    def update_progress(self, percent: int, message: str = ''):
        """更新进度条"""
        ...

    @abstractmethod
    def log(self, message: str, level: str = 'info'):
        """记录日志（info/warn/error/debug/success）"""
        ...

    # ==================== 弹窗 ====================

    @abstractmethod
    def show_error(self, title: str, message: str):
        """显示错误弹窗"""
        ...

    @abstractmethod
    def show_info(self, title: str, message: str):
        """显示信息弹窗"""
        ...

    @abstractmethod
    def show_warning(self, title: str, message: str):
        """显示警告弹窗"""
        ...

    @abstractmethod
    def confirm_dialog(self, title: str, message: str) -> bool:
        """显示确认对话框，返回用户选择（True=确认, False=取消）"""
        ...

    @abstractmethod
    def prompt_dialog(self, title: str, message: str, default: str = '') -> Optional[str]:
        """显示输入对话框，返回用户输入（None=取消）"""
        ...

    # ==================== 按钮状态 ====================

    @abstractmethod
    def set_button_state(self, button_name: str, enabled: bool):
        """设置单个按钮的启用/禁用状态"""
        ...

    @abstractmethod
    def set_buttons_state(self, states: Dict[str, bool]):
        """批量设置按钮状态"""
        ...