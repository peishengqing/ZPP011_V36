import os
import sys
import json
from datetime import datetime


def get_version():
    config_path = os.path.join('config', 'version.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            version = data.get('version', 'v1.0')
            app_name = data.get('app_name', 'SmartAssistant')
            return f"{app_name}_{version}"
    return "ZPP011_Analyzer_v36.1"


def write_build_log(app_full_name):
    log_path = 'build_log.md'
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {app_full_name}.exe | Build Success\n")


def build():
    app_full_name = get_version()
    print(f"Building: {app_full_name}")

    opts = [
        'gui/events.py',
        '--onefile',
        '--name', app_full_name,
        '--clean',
        '--noconfirm',
        '--hidden-import', 'pptx',
        '--hidden-import', 'pptx.util',
        '--hidden-import', 'pptx.dml.color',
        '--hidden-import', 'pptx.enum.text',
        '--hidden-import', 'ppt_generator',
        '--hidden-import', 'widgets',
        '--paths', os.path.dirname(os.path.abspath(__file__)),
    ]

    if os.path.exists('config'):
        opts.append('--add-data')
        opts.append('config;config')
        # 明确打包 config/version.json（防止遗漏）
        if os.path.exists('config/version.json'):
            opts.append('--add-data')
            opts.append('config/version.json;config')

    if os.path.exists('.zpp011_audit'):
        opts.append('--add-data')
        opts.append('.zpp011_audit;.zpp011_audit')

    if os.path.exists('app.ico'):
        opts.extend(['--icon', 'app.ico'])

    if os.path.exists('inventory_loader.py'):
        opts.append('--add-data')
        opts.append('inventory_loader.py;.')

    if os.path.exists('build_log.md'):
        opts.append('--add-data')
        opts.append('build_log.md;.')

    import PyInstaller.__main__
    PyInstaller.__main__.run(opts)

    write_build_log(app_full_name)
    print(f"Done: dist/{app_full_name}.exe")


if __name__ == '__main__':
    build()
