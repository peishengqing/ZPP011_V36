import py_compile
import sys

files = [
    "gui/event_handlers/table_events.py",
    "gui/event_handlers/analysis_events.py"
]

for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f"OK: {f}")
    except py_compile.PyCompileError as e:
        print(f"ERROR: {f}")
        print(e)
        sys.exit(1)

print("All files passed syntax check")
sys.exit(0)
