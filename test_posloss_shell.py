"""正损看板 DashboardShell + PosLossContent 组合冒烟测试（offscreen）"""
import sys
import os
sys.path.insert(0, 'E:/zpp011_v2')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import pandas as pd
from PySide6.QtWidgets import QApplication, QScrollArea

app = QApplication.instance() or QApplication([])

from gui_pyside6.widgets.pos_loss_content import PosLossContent
from gui_pyside6.components.dashboard_shell import DashboardShell
from gui_pyside6.controllers.dashboard_controller import DashboardController

class MockMainWindow:
    def _get_master_df(self):
        return build_df()

def build_df():
    # 覆盖正损/负损/未投料/疑似投错/持平 五种情形
    return pd.DataFrame({
        '工厂': ['F1'] * 6,
        '订单日期': ['2026-01-01'] * 6,
        '流程订单': ['P%d' % i for i in range(6)],
        '物料编码': ['400M%d' % i for i in range(6)],
        '物料名称': ['彩罐'] * 6,
        '物料描述': ['D'] * 6,
        '车间': ['C1'] * 6,
        '单位': ['个'] * 6,
        '数量-定额': [10.0, 10.0, 10.0, 0.0, 10.0, 10.0],
        '数量-实际': [12.0, 5.0, 0.0, 8.0, 10.0, 20.0],  # 超投/负损/未投料/疑似投错/持平/超投
        '备注': [''] * 6,
        '半成品重分类': [''] * 6,
        '_read': [0] * 6,
    })

# ① 组件可实例化 + 数据加载
mw = MockMainWindow()
content = PosLossContent(mw)
content.set_data(build_df())
assert content.original_df is not None, "set_data 失败"
print('① PosLossContent 实例化 + set_data OK')

# ② 正损口径：实际>定额 且 定额>0 → 只有 2 行 (12>10, 20>10)
mask = content._pos_loss_mask(content.original_df)
hits = int(mask.sum())
assert hits == 2, '正损口径错误: 期望 2 行，实际 %d 行' % hits
print('② 正损口径掩码 OK（命中 %d 行，正确排除负损/未投料/疑似投错/持平）' % hits)

# ③ 筛选后状态条实时更新（第二期：命中数/条件数一并回灌外壳）
shell = DashboardShell()
shell.set_title('正损(超投)看板')
content.attach_shell(shell)          # 控件归位到常驻条 + 抽屉 + 操作条
shell.set_content(content)
shell.set_status('已加载正损数据 · 共 6 条记录')
content._initializing = False
content._read_filter = "全部"       # 避开默认「未读」把测试行全滤掉
content._keywords = "彩罐"
content._apply_filter()
status = shell._status_label.text()
assert '共 2 条' in status, '状态条未实时更新: %s' % status
assert shell.lbl_total_hit.text() == '共 2 条命中', shell.lbl_total_hit.text()
print('③ 状态条/总命中实时联动 OK（%s / %s）' % (status, shell.lbl_total_hit.text()))

# ③b 第二期验收：常驻条 ≤5 个看板控件、无横向滚动筛选栏、抽屉分组齐全
bar_n = len([s for s in shell._filters.values() if s.zone == 'bar'])
assert bar_n == len(PosLossContent.BAR_FILTERS) == 5, bar_n
assert not content.findChildren(QScrollArea), '筛选栏仍被装进横向滚动区'
assert set(g for g, *_ in PosLossContent.DRAWER_FILTERS) == {'material', 'org'}
print('③b 常驻控件 %d 个、无横向滚动、抽屉分组 material+org OK' % bar_n)

# ③c 逐条件命中徽章：抽屉里每个条件都能看到自己放行多少行
content._read_filter = "未读"
content._apply_filter()
badge = shell._filters['quar'].badge.text()
assert badge.endswith('条'), badge
print('③c 抽屉命中徽章 OK（隔离区 %s）' % badge)

# ④ 快捷键存在
assert hasattr(content, '_sc_export') and content._sc_export.key().toString() == 'Alt+V'
assert hasattr(content, '_sc_refresh') and content._sc_refresh.key().toString() == 'F5'
print('④ 快捷键 Alt+V / F5 OK')

# ⑤ 控制器走新组合（不再引用旧对话框）
import inspect
src = inspect.getsource(DashboardController._show_pos_loss_dashboard)
assert 'PosLossContent' in src and 'DashboardShell' in src
assert 'PosLossDashboardDialog' not in src
print('⑤ DashboardController 已切到新组合 OK')

# ⑥ 主题切换
shell.set_theme('dark')
assert shell.get_theme() == 'dark'
shell.set_theme('light')
assert shell.get_theme() == 'light'
print('⑥ 亮暗主题切换 OK')

print('=' * 60)
print('✅ 正损看板 DashboardShell + PosLossContent 全部冒烟通过')
