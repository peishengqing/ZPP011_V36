# -*- coding: utf-8 -*-
"""探针3：产品代码原样（无 monkeypatch），验证排序角标+漏斗真屏渲染。"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ.pop("QT_QPA_PLATFORM", None)
import pandas as pd
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QTableView

app = QApplication.instance() or QApplication([])
from gui_pyside6.models.data_frame_model import DataFrameModel, AuditProxyModel
from gui_pyside6.widgets.sort_badge_header import SortBadgeHeader

rng = __import__("random").Random(1)
df = pd.DataFrame({
    "_read": [rng.choice([0,1]) for _ in range(200)],
    "工厂": [rng.choice(["上海","广州"]) for _ in range(200)],
    "车间": [f"{i%5}车间" for i in range(200)],
    "物料名称": [f"物料{i:04d}" for i in range(200)],
    "偏差率(%)": [round(rng.uniform(-20,20),3) for _ in range(200)],
})
sm = DataFrameModel(); sm.setDataFrame(df)
proxy = AuditProxyModel(); proxy.setSourceModel(sm)
proxy.setDynamicSortFilter(False)

view = QTableView()
view.resize(760, 420)
view.setWindowTitle("ZPP011 表头探针3")
view.move(200, 200)

header = SortBadgeHeader(Qt.Horizontal, view)
view.setHorizontalHeader(header)
view.setModel(proxy)
header.set_sort_columns_getter(lambda: [(1, True)])          # 工厂列(1) 排序 → 1▲
header.set_filtered_columns_getter(lambda: {2, 4})           # 车间/偏差率 已筛 → 漏斗

def grab():
    header.update()
    app.processEvents()
    pm = view.grab()
    print("grab null:", pm.isNull(), flush=True)
    if not pm.isNull():
        pm.save(r"H:\zpp011_v2\_header_probe3.png")
        print("saved", flush=True)
    os._exit(0)

view.show()
QTimer.singleShot(2500, grab)
QTimer.singleShot(20000, lambda: os._exit(0))
app.exec()
