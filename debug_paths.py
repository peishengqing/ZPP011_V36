import sys, os
with open(r'E:\zpp011_dev\模块化脚本\gui\events.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the _get_mode_config_dir import and usage
idx = content.find('_get_mode_config_dir')
if idx >= 0:
    print("=== _get_mode_config_dir usage ===")
    print(content[max(0,idx-100):idx+200])
else:
    print("NOT FOUND")

# Check if run_app uses _MEIPASS for version.json
idx2 = content.find('version.json')
if idx2 >= 0:
    print("\n=== version.json references ===")
    # Find all
    start = 0
    while True:
        pos = content.find('version.json', start)
        if pos < 0: break
        print(f"  At {pos}: ...{content[max(0,pos-80):pos+30]}...")
        start = pos + 10
