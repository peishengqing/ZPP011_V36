# -*- coding: utf-8 -*-
"""v43.152 排查4：复刻「Qt.Tool 置顶弹窗 hide() 之后调模态 exec()」的真实时序。

这是 v42.20「未读弹窗修复」时引入的写法，本脚本验证它在
模态对话框真开（exec 阻塞）的情况下能否正常弹出。
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"E:\zpp011_v2")

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtWidgets import QApplication, QDialog, QWidget, QVBoxLayout, QLabel, QPushButton

app = QApplication([])

print("=" * 72)
print("场景：popup(Qt.Tool + StaysOnTop) → hide() → 调 modal.exec_()")
print("=" * 72)

# 模拟模态看板
class Board(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("看板（模态）")
        v = QVBoxLayout(self)
        v.addWidget(QLabel("我是看板内容"))
        b = QPushButton("关闭")
        b.clicked.connect(self.accept)
        v.addWidget(b)
        self.shown = False

    def showEvent(self, e):
        self.shown = True
        super().showEvent(e)


board = Board()
board_exec_called = {"v": False, "exec_returned": None, "shown": False}


def open_board_like_real():
    """复刻 _show_deviation_warning_dialog：dialog.exec()"""
    board_exec_called["v"] = True
    # 模拟 exec 阻塞 300ms 后用户关闭
    QTimer.singleShot(300, board.accept)
    r = board.exec()
    board_exec_called["exec_returned"] = int(r)
    board_exec_called["shown"] = board.shown


# 模拟 popup
popup = QWidget()
popup.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
pv = QVBoxLayout(popup)
pv.addWidget(QLabel("未读概览"))

popup.show()
app.processEvents()
print("popup 初始可见:", popup.isVisible(), "flags StaysOnTop:",
      bool(popup.windowFlags() & Qt.WindowStaysOnTopHint))

# 复刻 _open_board
popup.hide()
print("hide() 后可见:", popup.isVisible())
open_board_like_real()
app.processEvents()

print("\n结果：")
print("  exec 被调用:", board_exec_called["v"])
print("  exec 返回值:", board_exec_called["exec_returned"], "(1=Accepted)")
print("  看板 showEvent 触发过:", board_exec_called["shown"] or board.shown)
if not board.shown:
    print("  ❌ 看板从未真正显示 → 用户看到的就是「点了没反应」")
else:
    print("  ✅ 看板正常显示")

print("\n" + "=" * 72)
print("Qt 行为说明")
print("=" * 72)
print("""
Qt.Tool + WindowStaysOnTopHint 的窗口在 hide() 后，
其 owner（parent）链上的模态对话框本应照常显示。

真正的问题不在 Qt，而在**异常被静默吞掉**：

  _open_board:
      self.hide()
      try:
          callback()          # ← 这里面 dialog.exec() 阻塞
      except Exception:
          pass                # ← 真实异常消失得无影无踪
      if not self._closed:
          self.show()        # ← 无论成败都恢复

`_show_audit_changes_dialog` 里有防重入标志 `_audit_changes_dialog_open`，
若之前某次打开中途异常，标志**没被重置**（没有 try/finally），
后续所有点击都会被 `if getattr(...): return` 直接静默返回 —— 永久失灵。

这才是「现在都不定位了」的最可能原因。
""")
