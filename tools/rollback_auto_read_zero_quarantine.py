# -*- coding: utf-8 -*-
"""v43.330 一次性回滚脚本：清掉被错误自动已读的「实际=0（未投料/非耗用）」隔离记录。

背景（裴哥 2026-11-10）：隔离区失效复核 + 已读对账逻辑曾把 `实际<=0` 的记录误判为
「实际已归零/已解决」并自动标已读、建议移出隔离区，与「实际=0 须人工审计、绝不自动已读」
的规则严重冲突。代码已修复（core/quarantine_manager.py、quarantine_manager_controller.py），
本脚本负责把**活库里已经发生的脏数据**翻回未读，呼应用户「回到昨天状态」的诉求。

判定目标（自包含，无需重载主表）：
  read_status.is_read = 1
  AND read_status.read_source = 'auto'
  AND (read_status.snapshot_qty IS NULL OR snapshot_qty <= 0)   # 自动已读时存的就是当时实际数量
  AND data_id 仍在隔离区（quarantine_records.restored_at IS NULL）

处置：UPDATE read_status SET is_read=0, read_source=''（保留 fingerprint / snapshot_* 等其它列）。

安全：执行前先把 audit.db 复制成 audit.db.bak.<UTC时间戳> 再动手。
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone

try:
    from core.read_status import DB_PATH
except Exception:
    DB_PATH = os.path.join(os.path.expanduser("~"), ".zpp011_audit", "audit.db")


def main():
    if not os.path.exists(DB_PATH):
        print(f"[ERR] audit.db 不存在: {DB_PATH}")
        return 1

    # ── 1. 备份 ──
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bak = f"{DB_PATH}.bak.{ts}"
    shutil.copy2(DB_PATH, bak)
    print(f"[OK] 已备份 audit.db -> {bak}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # ── 2. 仍在隔离区的 uid 集合 ──
    quarantined = {r[0] for r in cur.execute(
        "SELECT uid FROM quarantine_records WHERE restored_at IS NULL")}
    print(f"[INFO] 隔离区在册记录数: {len(quarantined)}")

    # ── 3. 候选：自动已读 + snapshot<=0 ──
    candidates = cur.execute(
        "SELECT data_id, snapshot_qty FROM read_status "
        "WHERE is_read=1 AND read_source='auto' "
        "AND (snapshot_qty IS NULL OR snapshot_qty <= 0)").fetchall()
    targets = [r[0] for r in candidates if r[0] in quarantined]
    print(f"[INFO] 候选(自动已读+snapshot<=0): {len(candidates)}  其中仍在隔离区: {len(targets)}")

    if not targets:
        print("[INFO] 无需要回滚的记录，结束。")
        conn.close()
        return 0

    # ── 4. 回滚前统计（仍quarantined的自动已读总数，用于核对）──
    before = cur.execute(
        "SELECT COUNT(*) FROM read_status "
        "WHERE is_read=1 AND read_source='auto' "
        "AND data_id IN (%s)" % ",".join("?" * len(quarantined)),
        list(quarantined)).fetchone()[0]

    # ── 5. 执行回滚 ──
    cur.executemany(
        "UPDATE read_status SET is_read=0, read_source='' WHERE data_id=?",
        [(t,) for t in targets])
    conn.commit()

    after = cur.execute(
        "SELECT COUNT(*) FROM read_status "
        "WHERE is_read=1 AND read_source='auto' "
        "AND data_id IN (%s)" % ",".join("?" * len(quarantined)),
        list(quarantined)).fetchone()[0]
    conn.close()

    print(f"[OK] 已翻回未读 {len(targets)} 条（data_id 样例见下）。")
    print(f"[INFO] 隔离区自动已读记录: 回滚前 {before} -> 回滚后 {after}")
    for t in targets[:20]:
        print("      ", t)
    if len(targets) > 20:
        print(f"      ... 共 {len(targets)} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
