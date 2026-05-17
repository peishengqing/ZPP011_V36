# -*- coding: utf-8 -*-
# core/logger.py
import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

_LOG_DIR = "logs"
os.makedirs(_LOG_DIR, exist_ok=True)


def _get_log_file_path():
    """按天生成日志文件，如 logs/2026-05-17.log"""
    return os.path.join(_LOG_DIR, f"{datetime.now().strftime('%Y-%m-%d')}.log")


def get_logger(name: str = "ZPP011") -> logging.Logger:
    """获取日志记录器，同时输出到控制台和文件"""
    logger = logging.getLogger(name)
    if logger.handlers:  # 避免重复添加
        return logger

    logger.setLevel(logging.DEBUG)

    # 文件处理器（按天滚动，保留30天）
    file_handler = TimedRotatingFileHandler(
        _get_log_file_path(),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    file_handler.setFormatter(file_formatter)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
