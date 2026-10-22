# -*- coding: utf-8 -*-
"""v43.153 排查：popup(parent=MainWindow, Qt.Tool) → hide() → 调 MainWindow 的模态 dialog

复刻 _show_unread_summary 的真实构造：UnreadSummaryPopup(items, self)
→ setWindowFlags(Qt.Window|Frameless|WindowStaysOnTop|Tool)
→ show()
→ 点「查看」→ self.hide() → callback() → callback 内 self._open_xxx_dialog()
   其中 _open_quarantine_dialog 里是 QuarantineDialog(qdf, self, self) + dlg.exec_()

关键怀疑：Qt.Tool 窗口作为 parent 的模态对话框，在 Windows 上可能
拿不到焦点/激活，或直接被 Tool 窗口遮挡。
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"E:\zpp011_v2")

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QDialog,
                               QVBoxLayout, QLabel, QPushButton)
from PySide6.QtTest import QTest

app = QApplication([])

EV = {"popup_shown": 0, "board_shown": 0, "board_focus": 0, "activated": []}


class Board(QDialog):
    """模拟隔离区窗口：QDialog(parent=MainWindow) + 模态。"""

    def __init__(self, mw):
        super().__init__(mw)
        self.setWindowTitle("隔离区（模拟）")
        v = QVBoxLayout(self)
        v.addWidget(QLabel("表格内容"))
        b = QPushButton("关闭")
        b.clicked.connect(self.accept)
        v.addWidget(b)

    def showEvent(self, e):
        EV["board_shown"] += 1
        super().showEvent(e)

    def focusInEvent(self, e):
        EV["board_focus"] += 1
        super().focusInEvent(e)


class MW(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("主窗")
        w = QWidget(self)
        self.setCentralWidget(w)
        QPushButton("占位", w).setGeometry(10, 10, 100, 30)

    def open_board(self):
        d = Board(self)
        EV["activated"].append("exec_前 isActiveWindow=%s" % self.isActiveWindow())
        d.exec_()


mw = MW()
mw.show()
app.processEvents()

# 复刻 UnreadSummaryPopup 的 flags
popup = QWidget(mw)
popup.setWindowFlags(Qt.Window | Qt.FramelessWindowHint |
                     Qt.WindowStaysOnTopHint | Qt.Tool)
v = QVBoxLayout(popup)
btn = QPushButton("查看", popup)
v.addWidget(btn)


def popup_showEvent(e):
    EV["popup_shown"] += 1
    super(popup, popup).showEvent(e) if False else None


def on_click():
    # 复刻 _open_board
    popup.hide()
    app.processEvents()
    mw.open_board()          # 内含 d.exec_() 阻塞
    # 回来后
    if not EV["activated"]:
        EV["activated"].append("exec 未完成")


btn.clicked.connect(on_click)

popup.show()
popup.raise_()
popup.activateWindow()
app.processEvents()

print("=" * 72)
print("初始状态")
print("=" * 72)
print("  popup 可见:", popup.isVisible(), "isActiveWindow:", popup.isActiveWindow())
print("  popup flags 含 Tool:", bool(popup.windowFlags() & Qt.Tool))
print("  popup flags 含 StaysOnTop:", bool(popup.windowFlags() & Qt.WindowStaysOnTopHint))
print("  parent 是 MW:", popup.parentWidget() is mw)

print("\n" + "=" * 72)
print("点「查看」：popup.hide() → mw.open_board() → d.exec_()")
print("=" * 72)

# 模态 exec 会阻塞，用定时器在 200ms 后关闭
def closer():
    for w in app.topLevelWidgets():
        if isinstance(w, Board) and w.isVisible():
            w.accept()

QTimer.singleShot(200, closer)
QTest.mouseClick(btn, Qt.LeftButton, pos=QPoint(5, 5))
app.processEvents()

print("  popup_shown 计数:", EV["popup_shown"])
print("  board_shown 计数:", EV["board_shown"], "← 0 表示模态窗口从未显示")
print("  board_focus 计数:", EV["board_focus"])
print("  轨迹:", EV["activated"])

print("\n" + "=" * 72)
print("结论")
print("=" * 72)
if EV["board_shown"] == 0:
    print("  ❌ 模态 Board 从未 showEvent → 用户点「查看」屏幕上什么都不出现")
    print("     根因方向：Qt.Tool 置顶窗口 hide() 后，其模态子对话框在 Windows 上被吞")
else:
    print("  ✅ 模态窗口正常显示")

print("\n" + "=" * 72)
print("补充检查：Qt.Tool 窗口本身作为「可见的模态阻塞者」是否影响 exec_")
print("=" * 72)
print("  复刻真实场景时，popup 的 parent=mw（MainWindow），")
print("  而 Board 的 parent 也是 mw —— 两层 hide/模态交互可能出问题。")
