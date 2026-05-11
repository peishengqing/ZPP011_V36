# -*- coding: utf-8 -*-
"""
v36 统一日志规范
⚠️ 不负责业务逻辑，只负责日志输出
"""

import logging
import os
from config.paths import TEMP_DIR

LOG_FILE = os.path.join(TEMP_DIR, "zpp011.log")


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的 logger 实例"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        # 控制台 handler（INFO 及以上）
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # 文件 handler（DEBUG 及以上）
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setLevel(logging.DEBUG)

        # 统一格式
        fmt = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            "%Y-%m-%d %H:%M:%S"
        )

        ch.setFormatter(fmt)
        fh.setFormatter(fmt)

        logger.addHandler(ch)
        logger.addHandler(fh)

    return logger


# ============================================================
# 日志级别使用规范
# ============================================================
#
# DEBUG  开发调试、变量值、详细流程
# INFO   正常流程节点（启动、分析、结束）
# WARNING 不影响主流程的问题（文件不存在等）
# ERROR  明确失败，但还能跑（数据库写入失败等）
# CRITICAL 程序必须终止（严重错误）
#
# ============================================================
# 各层 logger 使用示例
# ============================================================
#
# GUI 层：
#   from logger import get_logger
#   log = get_logger("gui")
#   log.info("GUI 启动成功")
#
# 分析层：
#   from logger import get_logger
#   log = get_logger("analysis")
#   log.debug(f"读取文件：{file_path}")
#
# 存储层：
#   from logger import get_logger
#   log = get_logger("storage")
#   log.exception("数据库写入失败")  # 自动打印堆栈
#
# ============================================================
