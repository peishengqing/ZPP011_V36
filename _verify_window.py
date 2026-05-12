import subprocess, sys, time, ctypes
from ctypes import windll

exe_path = r"E:\zpp011_dev\模块化脚本\dist\偏差分析+库存流水智能助手_v36.1.exe"
proc = subprocess.Popen([exe_path], creationflags=subprocess.CREATE_NEW_CONSOLE)

for i in range(15):
    time.sleep(1)
    if proc.poll() is not None:
        print(f"EXITED with code {proc.returncode}")
        break
    user32 = windll.user32
    EnumWindows = user32.EnumWindows
    GetWindowTextW = user32.GetWindowTextW
    windows = []
    def callback(hwnd, lParam):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length+1)
            GetWindowTextW(hwnd, buff, length+1)
            title = buff.value
            if title and len(title) > 3:
                windows.append(title)
        return True
    EnumWindows(lambda h,l: callback(h,l), 0)
    if windows:
        print(f"[second {i+1}] WINDOWS: {windows[:5]}")
        break
else:
    print(f"Still running after 15s, PID={proc.pid}")
    proc.terminate()