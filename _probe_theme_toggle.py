# -*- coding: utf-8 -*-
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import sys
REPO = r"E:/zpp011_v2"
sys.path.insert(0, REPO)
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
from utils.theme_manager import Thm
from gui_pyside6.main_window import MainWindow
win = MainWindow()
print("After MainWindow init - Thm.is_dark:", Thm.is_dark)
win._toggle_theme()
print("After first toggle - Thm.is_dark:", Thm.is_dark)
win._toggle_theme()
print("After second toggle - Thm.is_dark:", Thm.is_dark)
