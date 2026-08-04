import sys, os, re, traceback
sys.path.insert(0, r"E:/zpp011_v2")
os.environ["QT_QPA_PLATFORM"] = "offscreen"

def emit(lines):
    sys.stdout.write("\n".join(lines) + "\n")

try:
    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    from gui_pyside6.main_window import MainWindow
    w = MainWindow()
    lbl = w._analysis_time_label
    init_ok = (lbl.text() == "🕒 分析：—")
    emit(["INIT_OK=" + str(init_ok)])

    w._update_analysis_time_label("手动")
    t1 = lbl.text()
    ok1 = t1.startswith("XX")  # placeholder, recompute below safely
    try:
        ok1 = t1.startswith("🕒 分析：手动 ") and bool(re.match(r"\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", t1.split("手动 ")[1]))
    except Exception:
        ok1 = False
    emit(["MANUAL_OK=" + str(ok1)])

    w._monitor_auto_loading = True
    w._update_analysis_time_label("自动")
    t2 = lbl.text()
    try:
        ok2 = t2.startswith("🕒 分析：自动 ") and bool(re.match(r"\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", t2.split("自动 ")[1]))
    except Exception:
        ok2 = False
    emit(["AUTO_OK=" + str(ok2)])

    w._monitor_auto_loading = True
    mode_a = "自动" if getattr(w, "_monitor_auto_loading", False) else "手动"
    w._monitor_auto_loading = False
    mode_m = "自动" if getattr(w, "_monitor_auto_loading", False) else "手动"
    emit(["CAPTURE_AUTO=" + mode_a])
    emit(["CAPTURE_MANUAL=" + mode_m])
    emit(["RESULT=" + ("PASS" if (init_ok and ok1 and ok2 and mode_a == "自动" and mode_m == "手动") else "FAIL")])
except Exception:
    emit(["EXC_START"])
    emit([traceback.format_exc()])
    emit(["EXC_END"])
sys.exit(0)
