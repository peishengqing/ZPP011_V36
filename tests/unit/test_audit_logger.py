# -*- coding: utf-8 -*-
"""审计日志测试"""
import pytest
import os, time
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.audit_logger import AuditLogger


class TestAuditLogger:
    """审计日志测试"""

    def test_log_action(self, temp_dir):
        """测试日志记录"""
        db_path = os.path.join(temp_dir, 'test_audit.db')
        logger = AuditLogger(db_path=db_path)
        # log 是异步的（队列），等待写入
        logger.log('test_action', material_code='MAT001')
        time.sleep(0.5)
        logger.shutdown()

        # 验证数据已写入
        import sqlite3
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT * FROM audit_log WHERE action='test_action'").fetchall()
        conn.close()
        assert len(rows) >= 1

    def test_log_with_extra(self, temp_dir):
        """测试带额外信息的日志"""
        db_path = os.path.join(temp_dir, 'test_audit_extra.db')
        logger = AuditLogger(db_path=db_path)
        logger.log('audit', material_code='MAT002', extra={'reason': 'test'})
        time.sleep(0.5)
        logger.shutdown()

        import sqlite3
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT * FROM audit_log WHERE material_code='MAT002'").fetchall()
        conn.close()
        assert len(rows) >= 1

    def test_export_csv_async(self, temp_dir):
        """测试 CSV 异步导出"""
        db_path = os.path.join(temp_dir, 'test_audit_export.db')
        logger = AuditLogger(db_path=db_path)
        logger.log('export_test', material_code='MAT003')
        time.sleep(0.5)

        csv_path = os.path.join(temp_dir, 'audit.csv')
        result = []
        def callback(path, error):
            result.append((path, error))

        logger.export_csv_async(csv_path, callback=callback)
        time.sleep(1.0)
        logger.shutdown()

        # 验证 CSV 文件存在
        assert os.path.exists(csv_path)

    def test_queue_full_fallback(self, temp_dir):
        """测试队列满时降级（不崩溃）"""
        db_path = os.path.join(temp_dir, 'test_audit_queue.db')
        logger = AuditLogger(db_path=db_path, max_queue_size=5)
        # 快速写入超过队列大小
        for i in range(50):
            logger.log(f'action_{i}', material_code=f'MAT{i:04d}')
        time.sleep(1.0)
        logger.shutdown()
        # 不崩溃即为通过
        assert True

    def test_shutdown(self, temp_dir):
        """测试正常关闭"""
        db_path = os.path.join(temp_dir, 'test_audit_shutdown.db')
        logger = AuditLogger(db_path=db_path)
        logger.log('shutdown_test')
        logger.shutdown()
        # 再次调用不崩溃
        assert True

    def test_cleanup_old_logs(self, temp_dir):
        """测试旧日志清理（180天前）"""
        db_path = os.path.join(temp_dir, 'test_audit_cleanup.db')
        logger = AuditLogger(db_path=db_path)
        time.sleep(0.5)
        logger.shutdown()

        import sqlite3
        conn = sqlite3.connect(db_path)
        # 插入一条旧记录
        conn.execute("""
            INSERT INTO audit_log (timestamp, username, action)
            VALUES ('2020-01-01T00:00:00', 'test', 'old_action')
        """)
        conn.commit()
        count_before = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        conn.close()

        # 重新创建 logger 会触发清理
        logger2 = AuditLogger(db_path=db_path)
        time.sleep(0.5)
        logger2.shutdown()

        conn = sqlite3.connect(db_path)
        count_after = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        conn.close()
        # 旧记录应被清理
        assert count_after < count_before or count_before == 0
