# -*- coding: utf-8 -*-
import json, datetime

# Update version.json
ver_path = r'E:\zpp011_dev\模块化脚本\config\version.json'
with open(ver_path, 'r', encoding='utf-8') as f:
    ver = json.load(f)
ver['version'] = 'v36.1'
ver['release_notes'] = (
    "新增:库存流水界面完整实现(导入Excel/三表展示/汇总卡片/搜索过滤/全检报告)\n"
    "新增:库存流水界面顶部标题栏(与分析模式统一风格)\n"
    "修复:tkinter Frame构造函数pady元组参数错误导致界面崩溃\n"
    "修复:导入库存表按钮无反应(self.parent.log属性错误+表格填充未实现)\n"
    "修复:审核模块storage未定义错误\n"
    "修复:mode.json UTF-8 BOM编码问题\n"
    "修复:EXE打包后ModeSelector路径问题(sys._MEIPASS+用户目录)"
)
with open(ver_path, 'w', encoding='utf-8') as f:
    json.dump(ver, f, ensure_ascii=False, indent=2)

# Update build_log.md
log_path = r'E:\zpp011_dev\模块化脚本\build_log.md'
now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
entry = (
    "\n==================================================\n"
    + chr(0x1f4e5) + " v36.1 | " + now + " | 成功\n"
    + chr(0x1f4e4) + " 打包人：裴盛清\n"
    "--------------------------------------------------\n"
    " Python 3.11.9 | onefile | gui/events.py + gui/inventory_view.py | 44.8 MB |\n"
    "--------------------------------------------------\n"
    + chr(0x2705) + " 新增功能:\n"
    " 1. 库存流水界面完整实现(导入Excel/三表展示/汇总卡片/搜索过滤/全检报告)\n"
    " 2. 库存流水顶部标题栏(与分析模式统一风格)\n"
    + chr(0x1f6d1) + " 功能改进:\n"
    " 1. 版本号重置为v36.1\n"
    + chr(0x1f41e) + " Bug修复:\n"
    " 1. tkinter Frame构造函数pady元组参数错误导致界面崩溃\n"
    " 2. 导入库存表按钮无反应(self.parent.log属性错误+表格填充未实现)\n"
    " 3. 审核模块storage未定义错误(import storage缺失)\n"
    " 4. mode.json UTF-8 BOM编码问题\n"
    " 5. EXE打包后ModeSelector路径问题(sys._MEIPASS+用户目录)\n"
    "==================================================\n"
)
with open(log_path, 'a', encoding='utf-8') as f:
    f.write(entry)

print("Done! version.json -> v36.1, build_log updated")
