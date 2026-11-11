# -*- coding: utf-8 -*-
"""统一确认 / 提示 / 错误弹窗模板（设计稿 v43.333 第三期 · 弹窗体系「外壳四」）。

设计稿的三条规矩：
  1. 标题写「动词 + 对象 + 结果」，不再用「提示」「错误」这种没有信息量的词 ——
     用户扫一眼标题就知道发生了什么；
  2. 按钮写动作，不写「是 / 否」：「仍然标记」「删除预设」，按下去就知道会发生什么；
  3. 错误弹窗必须带可复制的技术详情（改造前只有一句 str(e)，截图反馈时也看不全）。

底层仍然是 QMessageBox：原生按钮布局、原生键盘行为（Enter=默认按钮、Esc=取消）、
原生跟随 app 级 light/dark QSS，这里只把文案与按钮角色规范化，不另起一套窗口。
技术详情由 Qt 自带的「显示详情」折叠区承载（可选中复制），另加一个「复制详情」
按钮一键进剪贴板 —— ActionRole 按钮点了不关窗，复制完还能接着看正文。
"""
from __future__ import annotations

from PySide6.QtWidgets import QApplication, QMessageBox

OK = "知道了"


def _build(parent, icon, title, text, actions, detail=None):
    """按 (文字, 角色) 列表装好一个 QMessageBox，返回 (box, {文字: 按钮})。

    第一个按钮吃默认焦点 —— 设计稿要求主操作在右下角且 Enter 可触发。
    """
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(text)
    if detail:
        box.setDetailedText(str(detail))
    buttons = {}
    for i, (label, role) in enumerate(actions):
        b = box.addButton(label, role)
        buttons[label] = b
        if i == 0:
            box.setDefaultButton(b)
    return box, buttons


def _clicked_label(box, buttons):
    box.exec()
    clicked = box.clickedButton()
    for label, b in buttons.items():
        if b is clicked:
            return label
    return None


def info(parent, title, text, ok=OK):
    """一句结论 + 一个离开按钮。标题必须写「做完了什么」。"""
    box, buttons = _build(parent, QMessageBox.Information, title, text,
                          [(ok, QMessageBox.AcceptRole)])
    return _clicked_label(box, buttons)


def warn(parent, title, text, detail=None, ok=OK):
    """提醒（不阻塞后续操作）：正文说清影响，标题说清发生了什么。"""
    box, buttons = _build(parent, QMessageBox.Warning, title, text,
                          [(ok, QMessageBox.AcceptRole)], detail=detail)
    return _clicked_label(box, buttons)


def error(parent, title, text, exc=None, detail=None, ok=OK):
    """错误弹窗：正文给人话，技术详情可折叠查看，「复制详情」一键进剪贴板。

    ``exc`` 直接传异常对象（详情写成 ``类型: 消息``），``detail`` 适合传已经拼好的
    日志片段 / 文件路径；两者都给时 detail 在前、exc 追加在后。
    """
    tech = []
    if detail:
        tech.append(str(detail))
    if exc is not None:
        tech.append("%s: %s" % (type(exc).__name__, exc))
    tech_text = "\n".join(tech) or str(text)
    box, buttons = _build(parent, QMessageBox.Critical, title, text,
                          [("复制详情", QMessageBox.ActionRole),
                           (ok, QMessageBox.AcceptRole)])
    # 关掉「显示详情」按钮重复出现的复制歧义：Qt 在 setDetailedText 后会自动加一个
    # 「显示详情」，这里保留它（能就地看全文），复制走我们自己那颗按钮。
    buttons["复制详情"].clicked.connect(
        lambda: QApplication.clipboard().setText("%s\n%s" % (title, tech_text)))
    return _clicked_label(box, buttons)


def confirm(parent, title, text, yes="确定", no="取消", detail=None, danger=False):
    """二选一确认：按钮写明动作，返回用户是否点了主动作。"""
    role = QMessageBox.DestructiveRole if danger else QMessageBox.AcceptRole
    box, buttons = _build(parent, QMessageBox.Question, title, text,
                          [(yes, role), (no, QMessageBox.RejectRole)], detail=detail)
    return _clicked_label(box, buttons) == yes


def ask(parent, title, text, labels, detail=None, danger=False):
    """多按钮选择：labels 第一个是主动作，返回被点按钮的文字（调用方按文字分支）。"""
    role = QMessageBox.DestructiveRole if danger else QMessageBox.AcceptRole
    actions = [(labels[0], role)] + [(t, QMessageBox.RejectRole) for t in labels[1:]]
    box, buttons = _build(parent, QMessageBox.Question, title, text, actions,
                          detail=detail)
    return _clicked_label(box, buttons)
