import sys, os, re, traceback
sys.path.insert(0, r"E:/zpp011_v2")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import time

RESULT = []
def log(msg):
    RESULT.append(msg)

try:
    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    from gui_pyside6.main_window import MainWindow
    w = MainWindow()
    lbl = w._analysis_time_label
    log("INIT_TEXT=" + lbl.text())
    log("INIT_OK=" + str(lbl.text() == "🕒 分析：—"))

    w._update_analysis_time_label("手动")
    t1 = lbl.text()
    ok1 = t1.startswith("🕒 分析：手动 ") and re.match(r"\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", t1.split("手动 ")[1]) is not None
    log("MANUAL_TEXT=" + t1)
    log("MANUAL_OK=" + str(ok1))

    w._monitor_auto_loading = True
    w._update_analysis_time_label("自动")
    t2 = lbl.text()
    ok2 = t2.startswith("🕒 分析：自动 ") and re.match(r"\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", t2.split("自动 ")[1]) is not None
    log("AUTO_TEXT=" + t2)
    log("AUTO_OK=" + str(ok2))

    # mode capture logic identical to _on_analysis_finished_ui top
    w._monitor_auto_loading = True
    mode_a = "自动" if getattr(w, "_monitor_auto_loading", False) else "手动"
    w._monitor_auto_loading = False
    mode_m = "自动" if getattr(w, "_monitor_auto_loading", False) else "手动"
    log("CAPTURE_AUTO=" + mode_a)
    log("CAPTURE_MANUAL=" + mode_m)
    log("CAPTURE_OK=" + str(mode_a == "自动" and mode_m == "手动"))

    # analyzing state
    w._monitor_auto_loading = True
    lbl.setText(f"🕒 分析中…（{'自动' if getattr(w,'_monitor_auto_loading',False) else '手动'}）")
    log("ANALYZING_TEXT=" + lbl.text())

    # fail state
    w._monitor_auto_loading = False
    lbl.setText(f"🕒 分析失败（{'自动' if getattr(w,'_monitor_auto_loading',False) else '手动'}）{time.strftime('%m-%d %H:%M:%S')}")
    log("FAIL_TEXT=" + lbl.text())

    log("RESULT=" + ("ALL_CORE_LOGIC_PASS" if (ok1 and ok2 and mode_a=="自动" and mode_m=="手动") else "FAIL"))
except Exception:
    log("EXCEPTION:\n" + traceback.format_exc())

with open(r"E:/zpp011_v2/verify_result.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(RESULT))
