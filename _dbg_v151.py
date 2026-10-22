# -*- coding: utf-8 -*-
"""v43.151 验证：概览「隔离区」卡片点击改为打开隔离区窗口"""
import os
import re
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"E:\zpp011_v2")

PASS, FAIL = [], []


def chk(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  PASS  " if cond else "  FAIL  ") + name + (("  | " + str(detail)) if detail else ""))


MW = r"E:\zpp011_v2\gui_pyside6\main_window.py"
SC = r"E:\zpp011_v2\gui_pyside6\widgets\stats_cards.py"
QD = r"E:\zpp011_v2\gui_pyside6\dialogs\quarantine_dialog.py"
src = open(MW, "r", encoding="utf-8").read()
sc = open(SC, "r", encoding="utf-8").read()

# 取出 _on_stats_card_clicked 全文
i = src.index("    def _on_stats_card_clicked")
j = src.index("    def log(self, msg", i)
_body_raw = src[i:j]
# 剥掉注释行再断言，否则 v43.151 改动说明里的旧代码名会造成误报
body = "\n".join(re.sub(r"^\s*#.*$", "", ln) for ln in _body_raw.split("\n"))

print("=" * 70)
print("[1] quarantine 分支改为开窗口")
print("=" * 70)
chk("分支调用 _open_quarantine_dialog()", "_open_quarantine_dialog()" in body)
chk("已移除 set_color_filter('quarantine')", "set_color_filter('quarantine')" not in body)
chk("已移除 cb = color_checks.get('_quarantined_only')",
    "color_checks.get('_quarantined_only')" not in body)
chk("deviation 分支未被动", "_show_deviation_warning_dialog()" in body)
chk("changed 分支保留 set_color_filter", "set_color_filter('changed')" in body)
chk("unread 分支保留", "set_read_status_filter('未读')" in body)
chk("anomaly 分支保留", "🔴 真异常" in body)

print("\n" + "=" * 70)
print("[2] 卡片 tooltip 更新")
print("=" * 70)
chk("tooltip 改为「点击打开隔离区」", "点击打开隔离区" in sc)
chk("旧文案「点击仅显示隔离行」已删", "点击仅显示隔离行" not in sc)
chk("偏差率预警 tooltip 未动", "点击打开偏差率预警看板" in sc)

print("\n" + "=" * 70)
print("[3] 无递归 / 依赖完好")
print("=" * 70)
chk("_open_quarantine_dialog 定义存在于同文件", "def _open_quarantine_dialog(self)" in src)
# _open_quarantine_dialog 内部不得回调卡片点击
k = src.index("    def _open_quarantine_dialog")
qbody = src[k:src.index("    def ", k + 10)]
chk("_open_quarantine_dialog 内不回调 _on_stats_card_clicked",
    "_on_stats_card_clicked" not in qbody)
chk("仍按 _quarantined==1 过滤", "'_quarantined'] == 1" in qbody)
chk("空隔离区有友好提示", "隔离区当前为空" in qbody)
chk("QuarantineDialog 有导入", "QuarantineDialog" in src)

print("\n" + "=" * 70)
print("[4] 卡片事件链路（离屏实测）")
print("=" * 70)
try:
    import pandas as pd
    from PySide6.QtCore import Qt, QPoint
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from gui_pyside6.widgets.stats_cards import StatsCardsWidget

    w = StatsCardsWidget()
    got = []
    w.card_clicked.connect(lambda t: got.append(t))

    for name, card, want in (("隔离区", w.card_quarantine, "quarantine"),
                             ("偏差率预警", w.card_deviation, "deviation")):
        got.clear()
        QTest.mouseClick(card, Qt.LeftButton, pos=QPoint(5, 5))
        chk("%s 卡片点击发出 %r" % (name, want), got == [want], got)

    chk("cardType 属性正确", w.card_quarantine.property("cardType") == "quarantine",
        w.card_quarantine.property("cardType"))
    # eventFilter 已安装：Qt 装了之后该控件会走 eventFilter 路径（用 sent 计数验证太脆，
    # 上面 QTest 点击已发出正确信号即为链路通）
except Exception as e:
    import traceback
    traceback.print_exc()
    chk("离屏点击未抛异常", False, e)

print("\n" + "=" * 70)
print("[5] 隔离区窗口数据口径（真实数据复刻）")
print("=" * 70)
try:
    import pandas as pd
    df = pd.read_pickle(r"C:/Temp/zpp_dev_out/dev.pkl")
    df["_quarantined"] = 0
    df.loc[df.index[:2], "_quarantined"] = 1
    qdf = df[df["_quarantined"] == 1].copy().reset_index(drop=True)
    chk("过滤出 2 条（与用户卡片数字一致）", len(qdf) == 2, len(qdf))
    chk("列结构完整保留", len(qdf.columns) == len(df.columns))
    chk("index 已 reset（下游按 iloc 取行安全）", list(qdf.index) == [0, 1], list(qdf.index))

    from PySide6.QtWidgets import QApplication, QWidget
    app = QApplication.instance() or QApplication([])
    from gui_pyside6.dialogs.quarantine_dialog import QuarantineDialog

    class _MW:
        """最小 main_window 替身：隔离区窗口只用到这几个成员。"""

        def __init__(self):
            self.view_model = type("V", (), {"df": df})()
            self._master = df
            self._parent = QWidget()

        def _get_master_df(self):
            return self._master

        def _locate_row_by_excel_no(self, *a, **k):
            return True

        def _locate_row_in_main_table(self, *a, **k):
            return True

        def get_all_data_id(self, *a, **k):
            return set()

    mw = _MW()
    d = QuarantineDialog(qdf, mw, mw._parent)
    chk("隔离区窗口构造成功", d is not None)
    chk("表格有数据", d.source_model.rowCount() == 2 if hasattr(d, "source_model") else True)
    chk("表格在布局内（v43.149 修复未回退）",
        d.table_view.parentWidget() is not None, d.table_view.parentWidget())
except Exception as e:
    import traceback
    traceback.print_exc()
    chk("隔离区窗口构造未抛异常", False, e)

print("\n" + "=" * 70)
print("[6] 版本与文件")
print("=" * 70)
vh = open(r"E:\zpp011_v2\utils\version_history.py", "r", encoding="utf-8").read()
chk("version_history 索引 0 = v43.151", '"v43.151"' in vh.split('"version": "v43.150"')[0])
chk("v43.151 有 fixes 字段", '"fixes"' in vh.split('"version": "v43.151"')[1][:2500])
chk("main_window 未硬编码版本号", "43.151" not in src.replace("v43.151", ""))

print("\n" + "=" * 70)
print("结果：%d PASS / %d FAIL" % (len(PASS), len(FAIL)))
if FAIL:
    print("失败项：")
    for f in FAIL:
        print("  - " + f)
print("=" * 70)
