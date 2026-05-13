import sys, os, traceback
_orig_excepthook = sys.excepthook

def _excepthook(exc_type, exc_value, exc_tb):
    err = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    log_path = os.path.join(os.path.expanduser('~'), 'Desktop', 'app_crash_early.log')
    try:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(err)
    except Exception:
        pass
    _orig_excepthook(exc_type, exc_value, exc_tb)

sys.excepthook = _excepthook
