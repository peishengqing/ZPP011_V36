#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File Service - 文件服务层

职责：
- 文件读取、保存、备份
- 路径处理、目录创建
- 文件验证（存在性、权限）

依赖：
- utils.helpers（纯工具函数）
"""

import os
import shutil
from datetime import datetime
from typing import Optional, List
from utils.helpers import standardize_remark


class FileService:
    """文件服务类"""
    
    def __init__(self):
        pass
    
    def ensure_directory(self, dir_path: str) -> str:
        """确保目录存在，不存在则创建
        
        Args:
            dir_path: 目录路径
        
        Returns:
            目录路径（绝对路径）
        """
        os.makedirs(dir_path, exist_ok=True)
        return dir_path
    
    def get_backup_path(self, file_path: str) -> str:
        """生成备份文件路径
        
        Args:
            file_path: 原文件路径
        
        Returns:
            备份文件路径（带时间戳）
        """
        dir_name = os.path.dirname(file_path)
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        ext = os.path.splitext(file_path)[1]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        backup_name = f"{base_name}_备份_{timestamp}{ext}"
        return os.path.join(dir_name, backup_name)
    
    def backup_file(self, file_path: str) -> Optional[str]:
        """备份文件
        
        Args:
            file_path: 原文件路径
        
        Returns:
            备份文件路径，失败返回 None
        """
        if not os.path.exists(file_path):
            return None
        
        try:
            backup_path = self.get_backup_path(file_path)
            shutil.copy2(file_path, backup_path)
            return backup_path
        except Exception as e:
            print(f"Backup failed: {e}")
            return None
    
    def find_latest_file(self, pattern: str, directory: str) -> Optional[str]:
        """查找匹配模式的最新文件
        
        Args:
            pattern: 文件名模式（如 "ZPP011 偏差分析最终版_*.xlsx"）
            directory: 搜索目录
        
        Returns:
            最新文件路径，未找到返回 None
        """
        import glob
        
        if not os.path.isdir(directory):
            return None
        
        search_pattern = os.path.join(directory, pattern)
        files = glob.glob(search_pattern)
        
        if not files:
            return None
        
        return max(files, key=os.path.getmtime)
    
    def validate_file(self, file_path: str, extensions: List[str] = None) -> bool:
        """验证文件
        
        Args:
            file_path: 文件路径
            extensions: 允许的扩展名列表（如 ['.xlsx', '.xls']）
        
        Returns:
            验证是否通过
        """
        if not os.path.exists(file_path):
            return False
        
        if extensions:
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in extensions:
                return False
        
        return True
