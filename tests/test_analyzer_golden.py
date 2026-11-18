# -*- coding: utf-8 -*-
"""黄金基线回归：analyzer 输出口径是否仍与基线一致。

对应 `tools/analyzer_golden_baseline.py`。基线文件缺失时自动跳过，
不阻塞他人本地跑全量测试；基线在红线模块改动前应重新 `--write`。

跑法：
    python -m pytest tests/test_analyzer_golden.py -q --no-cov
"""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, "tests", "fixtures", "golden", "analysis_baseline.json")
SCRIPT = os.path.join(ROOT, "tools", "analyzer_golden_baseline.py")


def test_analyzer_matches_golden_baseline():
    """分析结果的行数/偏差分布/金额合计等口径必须与基线逐项一致。"""
    if not os.path.isfile(BASELINE):
        pytest.skip("黄金基线不存在，先跑 tools/analyzer_golden_baseline.py --write")

    proc = subprocess.run(
        [sys.executable, SCRIPT, "--compare"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    if proc.returncode == 2:
        # 2 = 环境不匹配（输入文件或替代料配置与基线不一致），不是代码回归。
        # 例如在另一台机器上替代料配置不同，应跳过而不是报红。
        pytest.skip("基线环境不可用（输入/替代料配置与基线不一致）\n" + proc.stdout)
    if proc.returncode != 0:
        pytest.fail(
            f"分析口径偏离基线（exit={proc.returncode}）\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )
