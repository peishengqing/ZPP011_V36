# -*- coding: utf-8 -*-
"""
保存/导出防呆 —— 统一处理「目标文件正被其它程序占用」的情况。

背景：
    Windows 上 Excel / PowerPoint 打开一个文件后会**独占锁定**它，此时任何
    程序想覆盖写入都会抛 PermissionError，Python 原始报错长这样：

        [Errno 13] Permission denied: 'C:/Users/xxx/Desktop/偏差明细.xlsx'

    这句话普通用户看不懂，也不知道该怎么办。本模块把它翻译成人话，并提供
    「存为副本」兜底，让用户不必非得先去关 Excel。

用法（两种）：
    1) 直接落盘的场景 —— 用 safe_save，它负责预检 + 失败重试：
           from gui_pyside6.save_guard import safe_save
           final = safe_save(self, path, lambda p: df.to_excel(p, index=False))
           if final:   # None 表示用户取消
               toast(f"已导出到 {final}")

    2) 耗时任务（先算几十秒再落盘）—— 用 precheck_save_path，在开跑前就拦住，
       免得辛苦算完才发现写不进去：
           path = precheck_save_path(self, save_path, what="报告")
           if not path:
               return
"""
import os
import re
from datetime import datetime

from PySide6.QtWidgets import QMessageBox

__all__ = [
    'is_file_locked', 'make_copy_path', 'friendly_error',
    'precheck_save_path', 'safe_save', 'is_permission_error',
]

# 用户选择
_RETRY, _COPY, _CANCEL = 'retry', 'copy', 'cancel'


def is_permission_error(exc):
    """判断异常是否"写不进目标文件"这一类。

    注意：不能只 isinstance(exc, PermissionError)！
    pandas 用 xlsxwriter 引擎时，会把底层的 PermissionError 包装成
    xlsxwriter.exceptions.FileCreateError 再抛出；openpyxl 引擎则原样抛。
    所以这里同时看异常链和错误文本。
    """
    if isinstance(exc, PermissionError):
        return True
    seen = 0
    cur = exc
    while cur is not None and seen < 5:
        if isinstance(cur, PermissionError):
            return True
        cur = getattr(cur, '__cause__', None) or getattr(cur, '__context__', None)
        seen += 1
    text = f"{type(exc).__name__}: {exc}"
    return ('Errno 13' in text
            or 'Permission denied' in text
            or 'FileCreateError' in text)


def is_file_locked(path):
    """目标文件是否被其它程序独占锁定。

    文件不存在 或 能以写模式打开 → False（可以正常保存）。
    """
    if not path or not os.path.exists(path):
        return False
    try:
        with open(path, 'r+b'):
            return False
    except OSError:
        # PermissionError 是 OSError 子类；只读文件、无权限也走这里
        return True


def make_copy_path(path):
    """生成一个不冲突的副本路径：偏差明细.xlsx -> 偏差明细_1732.xlsx"""
    root, ext = os.path.splitext(path)
    # 去掉上一次自动加的时间后缀，避免 _1732_1733_1734 越堆越长
    root = re.sub(r'_\d{4}(\d{2})?$', '', root)
    now = datetime.now()
    for cand in (f"{root}_{now:%H%M}{ext}", f"{root}_{now:%H%M%S}{ext}"):
        if not os.path.exists(cand):
            return cand
    for i in range(2, 100):
        cand = f"{root}_{now:%H%M%S}_{i}{ext}"
        if not os.path.exists(cand):
            return cand
    return f"{root}_{now:%H%M%S}_x{ext}"


def friendly_error(path, exc=None):
    """把 PermissionError 之类的原始报错翻译成人话（用于日志/提示）。"""
    name = os.path.basename(path) if path else '文件'
    if exc is not None and not is_permission_error(exc):
        return f"保存「{name}」失败：{exc}"
    return (f"保存「{name}」失败：这个文件正被其它程序打开着"
            f"（多半还在 Excel 里没关），程序写不进去。")


def _ask(parent, path, what='文件'):
    """弹出人话提示，让用户选：重试 / 存为副本 / 取消。"""
    name = os.path.basename(path) or path
    copy_name = os.path.basename(make_copy_path(path))

    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle("保存不了 —— 文件正被占用")
    box.setText(f"「{name}」现在打不开写入，{what}没能保存。")
    box.setInformativeText(
        "最常见的原因：这个文件还在 Excel 里开着。\n"
        "Excel 打开文件时会把它独占锁住，别的程序就写不进去了。\n"
        "（少数情况是文件被设成了「只读」，或这个文件夹没有写入权限。）\n"
        "\n"
        "你可以二选一：\n"
        f"  • 去 Excel 里把「{name}」关掉，然后点【我已关闭，重试】\n"
        f"  • 不想关也行，点【存为副本】，改存成「{copy_name}」\n"
    )
    box.setDetailedText(f"完整路径：\n{path}")

    btn_retry = box.addButton("我已关闭，重试", QMessageBox.AcceptRole)
    btn_copy = box.addButton("存为副本", QMessageBox.ActionRole)
    box.addButton("取消", QMessageBox.RejectRole)
    box.setDefaultButton(btn_retry)
    box.exec()

    clicked = box.clickedButton()
    if clicked is btn_retry:
        return _RETRY
    if clicked is btn_copy:
        return _COPY
    return _CANCEL


def precheck_save_path(parent, path, what='文件'):
    """保存前预检：若目标被占用则引导用户处理。

    返回最终可用的路径；用户取消则返回 None。
    适合放在耗时任务（重新分析、生成 PPT）开始之前。
    """
    target = path
    while is_file_locked(target):
        choice = _ask(parent, target, what)
        if choice == _CANCEL:
            return None
        if choice == _COPY:
            target = make_copy_path(target)
        # _RETRY：循环回去重新检测
    return target


def safe_save(parent, path, save_fn, what='文件'):
    """带防呆的保存：预检 + 落盘 + 被占用时引导重试/存副本。

    Args:
        parent:  弹窗父窗口
        path:    用户选定的目标路径
        save_fn: 真正落盘的回调，签名 save_fn(final_path)
        what:    出现在提示里的名词，如「表格」「报告」

    Returns:
        实际保存成功的路径；用户取消返回 None。
        非权限类异常照常抛出，由调用方处理。
    """
    target = path
    while True:
        if is_file_locked(target):
            choice = _ask(parent, target, what)
            if choice == _CANCEL:
                return None
            if choice == _COPY:
                target = make_copy_path(target)
            continue

        try:
            save_fn(target)
            return target
        except Exception as e:
            # 只兜"文件被占用/没权限"这一类；其它异常（数据问题等）照常抛给调用方
            if not is_permission_error(e):
                raise
            choice = _ask(parent, target, what)
            if choice == _CANCEL:
                return None
            if choice == _COPY:
                target = make_copy_path(target)
            # _RETRY：循环回去再写一次
