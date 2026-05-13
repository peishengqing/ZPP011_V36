import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Delete or rename mode.json to force ModeSelector to show
mode_path = r'C:\Users\Administrator\.zpp011_audit\mode.json'
if os.path.exists(mode_path):
    # Rename it as backup instead of deleting
    backup = mode_path + '.bak'
    if os.path.exists(backup):
        os.remove(backup)
    os.rename(mode_path, backup)
    print(f"Renamed {mode_path} -> {backup}")
    print("ModeSelector will now show on next launch!")
else:
    print("mode.json not found - ModeSelector should already show")
