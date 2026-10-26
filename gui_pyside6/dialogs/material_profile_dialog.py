# -*- coding: utf-8 -*-
"""物料画像（v43.182）。

按「物料编码」聚合 `audit.db` 的三张表，为主表选中的物料生成一张「身份证」卡片：
累计偏差修改史、归因漂移、最近一次改了什么、进隔离次数 / 是否悬挂、最近标已读。
只读 `audit.db`，与偏差分析主表完全解耦，不触碰 analyzer 红线区。

⚠ 数据口径（已实跑核验，非推测）：
- `deviation_history.data_id` = 4 段：云南达利-食品厂|日期|订单|物料编码（含厂）
- `read_status.data_id` / `quarantine_records.uid` = 3 段：日期|订单|物料编码（**无厂段**）
故画像主键统一取「物料编码」（三表最后一列 `split('|')[-1]`），厂仅从 deviation_history 派生显示。
- `read_status` 记操作人字段名是 `user`（非 auditor），且实测值多为 'default'（用户维度未启用），
  故「最近标已读」只展示厂 + 时间，不承诺具体是谁。
"""
import os
import sqlite3
from collections import Counter

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QFrame, QScrollArea,
    QMessageBox,
)

_DB_PATH = os.path.join(os.path.expanduser("~"), ".zpp011_audit", "audit.db")


def _mat_of(key):
    """从 data_id / uid 取物料编码（最后一列）。脏数据 'X' / 空 → None。"""
    if not key or key == 'X':
        return None
    p = key.split('|')
    return p[-1].strip() if p else None


def _plant_of(did):
    """deviation_history 的 data_id 第 0 段含厂（云南达利-食品厂）；其余表无厂段。"""
    if not did or did == 'X':
        return ''
    p = did.split('|')
    if len(p) >= 4:
        return p[0].replace('云南达利-', '')
    return ''


def normalize_text(v):
    """把单元格值安全转成字符串（v43.184）。

    主表取出的物料编码/名称是 pandas 单元格值，可能是 numpy.int64 / float / NaN，
    直接调 `.strip()` 会抛 `'numpy.int64' object has no attribute 'strip'`。
    - numpy.int64 → '20005693'
    - float '20005693.0' → 去尾 .0 → '20005693'
    - NaN / None / 'nan' → ''（空串，交由上层走「未提供」分支）
    """
    if v is None:
        return ''
    s = str(v).strip()
    if not s or s.lower() in ('nan', 'none'):
        return ''
    if s.endswith('.0') and s[:-2].lstrip('-').isdigit():
        s = s[:-2]
    return s


class MaterialProfileDialog(QDialog):
    def __init__(self, code, parent=None, name=''):
        super().__init__(parent)
        self._code = normalize_text(code)   # v43.184 修：兼容 numpy.int64/float，勿直接 .strip()
        self._name = normalize_text(name)
        self.setWindowTitle("🪪 物料画像 — %s" % self._code)
        self.resize(560, 660)
        self._build_ui()
        self._load()

    # ---------- UI ----------
    def _build_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        body = QFrame()
        self._lay = QVBoxLayout(body)
        self._lay.setSpacing(10)
        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.addWidget(scroll)

    def _section(self, title):
        box = QGroupBox(title)
        inner = QVBoxLayout(box)
        inner.setSpacing(4)
        self._lay.addWidget(box)
        return inner

    def _kv(self, layout, k, v, warn=False):
        row = QHBoxLayout()
        row.addWidget(QLabel("<b>%s</b>" % k))
        val = QLabel(str(v))
        val.setWordWrap(True)
        if warn:
            val.setObjectName("profileWarnValue")
        row.addWidget(val, 1)
        layout.addLayout(row)

    def _empty(self, msg):
        self._lay.addWidget(QLabel("<i>%s</i>" % msg))

    # ---------- 数据 ----------
    def _load(self):
        if not self._code:
            self._empty("未提供物料编码")
            return
        if not os.path.exists(_DB_PATH):
            QMessageBox.information(self, "提示", "未找到审计库: %s" % _DB_PATH)
            return
        try:
            c = sqlite3.connect(_DB_PATH)
            dh = c.execute(
                "select data_id, field, old_value, new_value, change_reason, change_time "
                "from deviation_history where data_id is not null and data_id<>'X'").fetchall()
            q = c.execute(
                "select uid, reason, quarantined_at, restored_at from quarantine_records "
                "where uid is not null and uid<>'X'").fetchall()
            rs = c.execute(
                "select data_id, user, read_time from read_status "
                "where data_id is not null and data_id<>'X'").fetchall()
            c.close()
        except Exception as e:
            QMessageBox.critical(self, "错误", "读取审计库失败: %s" % e)
            return

        dh_rows = [r for r in dh if _mat_of(r[0]) == self._code]
        q_rows = [r for r in q if _mat_of(r[0]) == self._code]
        rs_rows = [r for r in rs if _mat_of(r[0]) == self._code]

        # 基本信息（厂仅从 deviation_history 派生）
        plants = sorted({_plant_of(r[0]) for r in dh_rows if _plant_of(r[0])})
        plant_txt = "、".join(plants) if plants else "（仅出现在已读/隔离表，无厂信息）"
        head = self._section("基本信息")
        self._kv(head, "物料编码", self._code)
        if self._name:
            self._kv(head, "物料名称", self._name)
        self._kv(head, "厂", plant_txt)

        if not (dh_rows or q_rows or rs_rows):
            self._empty("审计库中暂无该物料的任何记录（deviation_history / quarantine_records / "
                        "read_status 均无匹配）。")
            return

        # 偏差修改史
        if dh_rows:
            box = self._section("偏差修改史（deviation_history）")
            self._kv(box, "累计修改次数", len(dh_rows))
            note_cnt = sum(1 for r in dh_rows if r[1] == '备注原因')
            self._kv(box, "归因漂移（备注原因被改）", note_cnt)
            times = [r[5] for r in dh_rows if r[5]]
            if times:
                self._kv(box, "最近修改时间", max(times))
            latest = max(dh_rows, key=lambda r: r[5] or '')
            self._kv(box, "最近一次改了什么",
                     "字段[%s] %s → %s（原因：%s）"
                     % (latest[1], latest[2], latest[3], latest[4]))
            cr = Counter(r[4] for r in dh_rows if r[4])
            if cr:
                self._kv(box, "常见原因 Top3",
                         "；".join("%s(%d)" % (k, n) for k, n in cr.most_common(3)))
        else:
            self._empty("deviation_history：无该物料的偏差修改记录。")

        # 隔离区
        if q_rows:
            box = self._section("隔离区（quarantine_records）")
            self._kv(box, "进隔离次数", len(q_rows))
            hanging = [r for r in q_rows if not r[3]]
            if hanging:
                self._kv(box, "⚠ 悬挂未放回", "%d 次（restored_at 为空）" % len(hanging), warn=True)
            else:
                self._kv(box, "是否悬挂", "否（均已放回）")
            qtimes = [r[2] for r in q_rows if r[2]]
            if qtimes:
                self._kv(box, "最近进隔离时间", max(qtimes))
        else:
            self._empty("quarantine_records：该物料从未进隔离区。")

        # 审核已读
        if rs_rows:
            box = self._section("审核已读（read_status）")
            rtimes = [r[2] for r in rs_rows if r[2]]
            if rtimes:
                last = max(rtimes)
                users = {r[1] for r in rs_rows if r[1] and r[2] == last}
                self._kv(box, "最近标已读",
                         "%s（时间：%s）" % ("、".join(users) or "—", last))
            self._kv(box, "标已读总次数", len(rs_rows))
        else:
            self._empty("read_status：该物料无标已读记录。")
