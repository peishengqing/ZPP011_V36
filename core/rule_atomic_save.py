import os
import json
import shutil
import tempfile

def atomic_save_json(data: dict, file_path: str, backup_ext=".backup"):
    """
    原子保存 JSON 数据到文件
    流程: 校验 → 临时文件 → 备份 → 原子替换 → 清理
    """
    # 1. 校验序列化
    try:
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
    except Exception as e:
        raise ValueError(f"数据无法序列化为 JSON: {e}")

    # 2. 写入临时文件
    dir_name = os.path.dirname(file_path) or '.'
    fd, tmp_path = tempfile.mkstemp(suffix='.json', dir=dir_name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(json_str)
    except Exception as e:
        os.close(fd)
        os.remove(tmp_path)
        raise IOError(f"写入临时文件失败: {e}")

    # 3. 备份原文件
    backup_path = file_path + backup_ext
    has_backup = False
    if os.path.exists(file_path):
        shutil.copy2(file_path, backup_path)
        has_backup = True

    # 4. 原子替换
    try:
        os.replace(tmp_path, file_path)
    except Exception as e:
        if has_backup and os.path.exists(backup_path):
            shutil.copy2(backup_path, file_path)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise IOError(f"原子替换失败: {e}")

    # 5. 清理备份
    if has_backup and os.path.exists(backup_path):
        os.remove(backup_path)