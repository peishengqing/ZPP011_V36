"""打包脚本 — 版本号统一从 config/version.json 读取"""
import os
import sys
import json
import time
from datetime import datetime


def get_version_info():
    """从 config/version.json 读取版本号和名称"""
    config_path = os.path.join('config', 'version.json')
    result = {'version': 'v1.0', 'app_name': '智能助手', 'packed_by': '', 'release_notes': ''}
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        result['version'] = data.get('version', 'v1.0')
        result['app_name'] = data.get('app_name', '智能助手')
        result['packed_by'] = data.get('packed_by', '')
        result['release_notes'] = data.get('release_notes', '')
    return result


def get_version():
    """获取完整版本名"""
    info = get_version_info()
    return f"{info['app_name']}_{info['version']}"


def format_duration(seconds):
    """格式化耗时：秒 → X分X秒"""
    if seconds < 60:
        return f"{int(seconds)}秒"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}分{secs}秒"


def parse_release_notes(notes):
    """解析 release_notes，按前缀归类"""
    if not notes:
        return {'新增': [], '改进': [], '修复': [], '其他': []}
    
    categories = {'新增': [], '改进': [], '修复': [], '其他': []}
    for line in notes.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith('新增:'):
            categories['新增'].append(line[3:])
        elif line.startswith('改进:'):
            categories['改进'].append(line[3:])
        elif line.startswith('修复:'):
            categories['修复'].append(line[3:])
        else:
            categories['其他'].append(line)
    return categories


def write_build_log(app_full_name, success=True, duration_seconds=0, exe_size_mb=0):
    """写打包日志到 build_log.md（详细格式）"""
    info = get_version_info()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    version = info['version']
    app_name = info['app_name']
    packed_by = info['packed_by']
    release_notes = info['release_notes']
    
    # 解析更新内容
    categories = parse_release_notes(release_notes)
    
    # 构建日志块
    status_icon = '✅ 成功' if success else '❌ 失败'
    log_lines = [
        "=" * 50,
        f"📦 {version} | {now_str} | {status_icon}",
    ]
    
    # 打包人（如果有）
    if packed_by:
        log_lines.append(f"👤 打包人：{packed_by}")
    
    log_lines.append("-" * 50)
    
    # 元信息
    py_ver = f"Python {sys.version.split()[0]}"
    exe_size = f"{exe_size_mb:.1f} MB"
    duration = format_duration(duration_seconds)
    log_lines.append(f" {py_ver} | onefile | gui/events.py | {exe_size} | 耗时 {duration}")
    
    log_lines.append("-" * 50)
    
    # 更新内容（如果成功且有内容）
    if success and any(categories.values()):
        log_lines.append("✨ 新增功能：")
        for i, item in enumerate(categories['新增'], 1):
            log_lines.append(f" {i}. {item}")
        
        if categories['改进']:
            log_lines.append("")
            log_lines.append("🔧 功能改进：")
            for i, item in enumerate(categories['改进'], 1):
                log_lines.append(f" {i}. {item}")
        
        if categories['修复']:
            log_lines.append("")
            log_lines.append("🐛 Bug修复：")
            for i, item in enumerate(categories['修复'], 1):
                log_lines.append(f" {i}. {item}")
        
        if categories['其他']:
            log_lines.append("")
            log_lines.append("📋 其他变更：")
            for i, item in enumerate(categories['其他'], 1):
                log_lines.append(f" {i}. {item}")
    elif not success:
        log_lines.append("❌ 打包失败，请检查错误信息")
    else:
        log_lines.append("（本次无更新说明）")
    
    log_lines.append("=" * 50)
    log_lines.append("")  # 空行分隔
    
    # 追加写入
    log_content = '\n'.join(log_lines)
    log_path = 'build_log.md'
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(log_content + '\n')
    
    print(f"✅ 版本日志已更新：{log_path}")


def build():
    start_time = time.time()
    app_full_name = get_version()
    print(f"📦 开始打包：{app_full_name}")

    opts = [
        'gui/events.py',
        '--onefile',
        '--windowed',
        '--name', app_full_name,
        '--clean',
        '--noconfirm',
    ]

    # 资源文件
    if os.path.exists('config'):
        opts.append('--add-data')
        opts.append('config;config')

    if os.path.exists('.zpp011_audit'):
        opts.append('--add-data')
        opts.append('.zpp011_audit;.zpp011_audit')

    if os.path.exists('app.ico'):
        opts.extend(['--icon', 'app.ico'])

    if os.path.exists('inventory_loader.py'):
        opts.append('--add-data')
        opts.append('inventory_loader.py;.')

    # 打包日志
    if os.path.exists('build_log.md'):
        opts.append('--add-data')
        opts.append('build_log.md;.')

    import PyInstaller.__main__
    
    try:
        PyInstaller.__main__.run(opts)
        
        # 打包成功，计算耗时和文件大小
        duration = time.time() - start_time
        exe_path = os.path.join('dist', f'{app_full_name}.exe')
        exe_size = os.path.getsize(exe_path) / (1024 * 1024)  # MB
        
        write_build_log(app_full_name, success=True, duration_seconds=duration, exe_size_mb=exe_size)
        print(f"✅ 打包完成：dist/{app_full_name}.exe")
        
    except Exception as e:
        # 打包失败，写入日志
        duration = time.time() - start_time
        write_build_log(app_full_name, success=False, duration_seconds=duration)
        raise


if __name__ == '__main__':
    build()