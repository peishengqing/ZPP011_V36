# -*- coding: utf-8 -*-
"""测试 core/read_status.py 已读状态持久化"""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest


class TestReadStatusBasic:
    """测试 read_status 的保存和读取"""

    def test_save_and_load(self):
        """基本写入读取流程"""
        import core.read_status as rs

        # 使用临时文件隔离数据库
        orig_path = rs.DB_PATH
        tmp_db = os.path.join(tempfile.mkdtemp(), 'test_audit.db')
        rs.DB_PATH = tmp_db
        try:
            rs.save_read_status('test_id_1', 1, 'fp_v1')
            result = rs.load_read_status(['test_id_1'])
            assert 'test_id_1' in result
            assert result['test_id_1'] == (1, 'fp_v1')
        finally:
            rs.DB_PATH = orig_path
            if os.path.exists(tmp_db):
                os.remove(tmp_db)

    def test_load_empty_list(self):
        """空 ID 列表应返回空字典"""
        import core.read_status as rs

        orig_path = rs.DB_PATH
        tmp_db = os.path.join(tempfile.mkdtemp(), 'test_audit.db')
        rs.DB_PATH = tmp_db
        try:
            result = rs.load_read_status([])
            assert result == {}
        finally:
            rs.DB_PATH = orig_path
            if os.path.exists(tmp_db):
                os.remove(tmp_db)

    def test_missing_ids_return_default(self):
        """未保存的 ID 不应在结果中"""
        import core.read_status as rs

        orig_path = rs.DB_PATH
        tmp_db = os.path.join(tempfile.mkdtemp(), 'test_audit.db')
        rs.DB_PATH = tmp_db
        try:
            rs.save_read_status('id_exists', 1, 'fp')
            result = rs.load_read_status(['id_exists', 'id_ghost'])
            assert 'id_exists' in result
            assert 'id_ghost' not in result
        finally:
            rs.DB_PATH = orig_path
            if os.path.exists(tmp_db):
                os.remove(tmp_db)

    def test_overwrite_status(self):
        """重复保存相同 ID 应覆盖"""
        import core.read_status as rs

        orig_path = rs.DB_PATH
        tmp_db = os.path.join(tempfile.mkdtemp(), 'test_audit.db')
        rs.DB_PATH = tmp_db
        try:
            rs.save_read_status('test_id', 1, 'fp_v1')
            rs.save_read_status('test_id', 0, 'fp_v2')
            result = rs.load_read_status(['test_id'])
            assert result['test_id'] == (0, 'fp_v2')
        finally:
            rs.DB_PATH = orig_path
            if os.path.exists(tmp_db):
                os.remove(tmp_db)

    def test_multiple_ids(self):
        """批量读写多个 ID"""
        import core.read_status as rs

        orig_path = rs.DB_PATH
        tmp_db = os.path.join(tempfile.mkdtemp(), 'test_audit.db')
        rs.DB_PATH = tmp_db
        try:
            ids = [f'id_{i}' for i in range(5)]
            for i, id_ in enumerate(ids):
                rs.save_read_status(id_, i % 2, f'fp_{i}')

            result = rs.load_read_status(ids)
            assert len(result) == 5
            for i, id_ in enumerate(ids):
                assert result[id_] == (i % 2, f'fp_{i}')
        finally:
            rs.DB_PATH = orig_path
            if os.path.exists(tmp_db):
                os.remove(tmp_db)

    def test_init_db(self):
        """init_db 应能正常执行"""
        import core.read_status as rs

        orig_path = rs.DB_PATH
        tmp_db = os.path.join(tempfile.mkdtemp(), 'test_audit.db')
        rs.DB_PATH = tmp_db
        try:
            # 不应抛出异常
            rs.init_db()
        finally:
            rs.DB_PATH = orig_path
            if os.path.exists(tmp_db):
                os.remove(tmp_db)
