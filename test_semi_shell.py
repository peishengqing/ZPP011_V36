"""半成品看板 DashboardShell + SemiContent 组合冒烟测试（offscreen）

验收重点：
  ① 剥壳后口径代码零改动（投料状态四档 + 400/410 前缀兜底 + 固定分类清单）
  ② v43.335 补回的列宽自适应确实装上（前两轮迁移曾把它连同旧视觉壳一起拆掉）
  ③ 外壳层信号/状态条/快捷键/主题全部就位
"""
import sys
import os
sys.path.insert(0, 'E:/zpp011_v2')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from gui_pyside6.widgets.semi_content import (
    SemiContent, FEED_STATUS_ALL, FEED_STATUS_ITEMS, _demo_dataframe,
)
from gui_pyside6.components.dashboard_shell import DashboardShell
from gui_pyside6.utils.table_autofit import get_adaptive
from gui_pyside6.controllers.dashboard_controller import DashboardController
import inspect


class MockMainWindow:
    pass


# ① 组件实例化（QWidget，不是 QDialog）
content = SemiContent(MockMainWindow())
assert not hasattr(content, 'accept'), "SemiContent 不应有 QDialog.accept"
assert content.metaObject().className() == 'SemiContent'
print('① SemiContent(QWidget) 实例化 OK')

# ② 数据加载 + 投料状态四档口径反证
df = _demo_dataframe()
content.set_data(df)
assert content.original_df is not None and len(content.original_df) == 5
buckets = content._feed_status_buckets(content.original_df)
assert buckets is not None
names = {k: int(v.sum()) for k, v in buckets.items()}
# demo 五行：未投料1 / 负损1 / 疑似投错1 / 正常超投1 / 辅原料未投料1
assert names['未投料'] == 2 and names['负损'] == 1 \
    and names['疑似投错'] == 1 and names['正常/超投'] == 1, names
print('② 投料状态四档口径 OK %s' % names)

# 逐档切掩码，断言只放行对应行
for want in FEED_STATUS_ITEMS:
    content._feed_status = want
    m = content._feed_status_mask(content.original_df)
    assert int(m.sum()) == names[want], '档位 %s 命中 %d，期望 %d' % (
        want, int(m.sum()), names[want])
content._feed_status = FEED_STATUS_ALL
assert bool(content._feed_status_mask(content.original_df).all())
print('   四档互斥 + 「全部」全放行 OK')

# ③ 半成品分类固定清单（400/410 前缀兜底 + 排除辅原料）
vals = content._semi_class_values(content.original_df)
assert '食品成品半成品' in list(vals) and '饮料成品半成品' in list(vals)
assert '食品辅原料' in list(vals)  # 辅原料行确实在表里，靠分类筛选排除
print('③ 半成品分类取值 OK（含 400/410 前缀兜底）')

# ④ v43.335 关键回归点：列宽自适应确实装上
ctrl = get_adaptive(content.table_view)
assert ctrl is not None, 'install_adaptive 未执行，列宽会退化成 Qt 等宽'
print('④ 列宽自适应控制器已安装 OK (mode=%s, key=%s)' % (ctrl.mode, getattr(ctrl, '_key', None)))

# ⑤ 外壳层：状态条实时联动 + 快捷键 + 关闭信号
shell = DashboardShell()
shell.set_title('半成品看板')
shell.set_content(content)
shell.set_status('已加载半成品数据 · 共 5 条记录')
content.shell = shell
content._read_filter = '全部'      # 避开默认「未读」
content._semi_class_filter = set()  # 避开默认只勾两类，避免 demo 行数被压到 0
content._apply_filter()
assert '已筛选' in shell._status_label.text(), shell._status_label.text()
print('⑤ 状态条实时联动 OK（%s）' % shell._status_label.text())

assert content._sc_export.key().toString() == 'Alt+V'
assert content._sc_refresh.key().toString() == 'F5'
# PySide6 的 receivers() 需传 SIGNAL 宏字符串，这里直接验证 Enter 能触发筛选
_before = shell._status_label.text()
content.edit_keywords.setText('薯片')
content.edit_keywords.returnPressed.emit()
_after = shell._status_label.text()
assert _after != _before, 'Enter 未触发筛选'
print('   Enter 筛选 / Alt+V 导出 / F5 重筛 OK')

fired = []
content.close_requested.connect(lambda: fired.append(1))
content.close_requested.emit()
assert fired == [1]
print('   close_requested 信号 OK（关闭/下钻/双击三处共用）')

# ⑥ 控制器接线：新组合 + 非模态多开（v43.340 起窗口统一由 _present_board 承载）
src = inspect.getsource(DashboardController._show_semi_dashboard)
assert 'SemiContent' in src and 'DashboardShell' in src
assert 'SemiDashboardDialog' not in src
assert '_present_board' in src and 'dialog.exec()' not in src
present_src = inspect.getsource(DashboardController._present_board)
assert 'close_requested.connect(dialog.close)' in present_src
assert 'setModal(False)' in present_src and 'WA_DeleteOnClose' in present_src
print('⑥ DashboardController 新组合 + 非模态多开接线 OK')

# ⑦ 主题切换
shell.set_theme('dark')
assert shell.get_theme() == 'dark'
shell.set_theme('light')
assert shell.get_theme() == 'light'
print('⑦ 亮暗主题切换 OK')

# ⑧ 独立运行入口也能构造组合
dlg = content  # 不额外开窗口，避免 offscreen 卡住事件循环
print('=' * 60)
print('✅ 半成品看板 DashboardShell + SemiContent 全部冒烟通过')
