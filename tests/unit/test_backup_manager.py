# -*- coding: utf-8 -*-
"""备份管理测试"""
import pytest
import os, hashlib
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestBackupManagerStatic:
    """BackupManager 静态方法测试（不依赖 storage/GUI）"""

    def test_is_file_locked_nonexistent(self):
        """文件不存在 → 不被锁定"""
        from core.backup_manager import BackupManager
        assert BackupManager.is_file_locked('/nonexistent/file.txt') == False

    def test_is_file_locked_unlocked(self, temp_dir):
        """文件未被占用 → False"""
        from core.backup_manager import BackupManager
        test_file = os.path.join(temp_dir, 'test_unlocked.txt')
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write('test content')
        assert BackupManager.is_file_locked(test_file) == False

    def test_check_version_compatible_same_version(self):
        """版本一致 → 兼容"""
        from core.backup_manager import BackupManager
        meta = {'version': '1.0.0'}
        # 无 GUI 窗口时默认返回 True
        result = BackupManager.check_version_compatible(meta)
        assert result == True

    def test_check_version_compatible_no_version(self):
        """无版本号 → 默认允许"""
        from core.backup_manager import BackupManager
        meta = {}
        result = BackupManager.check_version_compatible(meta)
        assert result == True


class TestBackupManagerSync:
    """BackupManager 同步备份测试"""

    @pytest.mark.skip(reason="依赖 storage.py 和 GUI 环境")
    def test_backup_before_analysis_sync(self):
        """测试同步备份"""
        from core.backup_manager import BackupManager
        manager = BackupManager()
        # This requires real storage paths
        pass

    def test_md5_checksum(self, temp_dir):
        """测试 MD5 校验（辅助功能）"""
        test_file = os.path.join(temp_dir, 'test.txt')
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write('test content')
        with open(test_file, 'rb') as f:
            md5 = hashlib.md5(f.read()).hexdigest()
        assert len(md5) == 32
        # 相同内容 MD5 一致
        test_file2 = os.path.join(temp_dir, 'test2.txt')
        with open(test_file2, 'w', encoding='utf-8') as f:
            f.write('test content')
        with open(test_file2, 'rb') as f:
            md5_2 = hashlib.md5(f.read()).hexdigest()
        assert md5 == md5_2

    def test_file_copy_integrity(self, temp_dir):
        """测试文件拷贝完整性"""
        import shutil
        src = os.path.join(temp_dir, 'source.xlsx')
        dst = os.path.join(temp_dir, 'backup.xlsx')
        # 写入测试数据
        with open(src, 'wb') as f:
            f.write(os.urandom(1024))
        shutil.copy2(src, dst)
        # 校验 MD5 一致
        with open(src, 'rb') as f:
            md5_src = hashlib.md5(f.read()).hexdigest()
        with open(dst, 'rb') as f:
            md5_dst = hashlib.md5(f.read()).hexdigest()
        assert md5_src == md5_dst
