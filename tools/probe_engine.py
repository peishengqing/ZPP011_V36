"""正确路径：GetObject('SAPGUI').GetScriptingEngine()"""
import time
import win32com.client

def log(msg): print(f"[ENGINE] {msg}", flush=True)

try:
    sap_auto = win32com.client.GetObject("SAPGUI")
    log(f"SAPGUI object: {sap_auto}")
    for attr in ['GetScriptingEngine', 'Type', 'Children']:
        try:
            v = getattr(sap_auto, attr)
            log(f"  SAPGUI.{attr} exists -> {v}")
        except Exception as e:
            log(f"  SAPGUI.{attr} ERR: {type(e).__name__}")

    log("调用 GetScriptingEngine...")
    engine = sap_auto.GetScriptingEngine()
    log(f"engine = {engine}")
    for attr in ['Type', 'Children', 'Connections', 'Sessions', 'Name', 'Statusbar']:
        try:
            v = getattr(engine, attr)
            if hasattr(v, 'Count'):
                log(f"  engine.{attr}.Count = {v.Count}")
            else:
                log(f"  engine.{attr} = {v}")
        except Exception as e:
            log(f"  engine.{attr} ERR: {type(e).__name__}")

    if hasattr(engine, 'Children'):
        log(f"\n现有连接数: {engine.Children.Count}")
        for i in range(engine.Children.Count):
            c = engine.Children(i)
            log(f"  conn[{i}] Id={getattr(c,'Id','?')} Desc={getattr(c,'Description','?')}")
            for attr in ['Children', 'Sessions', 'IsConnected']:
                try:
                    v = getattr(c, attr)
                    if hasattr(v, 'Count'):
                        log(f"    conn.{attr}.Count = {v.Count}")
                    else:
                        log(f"    conn.{attr} = {v}")
                except Exception as e:
                    log(f"    conn.{attr} ERR: {type(e).__name__}")

    log("\n尝试 OpenConnection('PS4') ...")
    conn = engine.OpenConnection("PS4")
    log(f"OpenConnection OK: {conn}")
    for i in range(20):
        time.sleep(1)
        try:
            cnt = conn.Children.Count
            log(f"  wait {i+1}s: Children.Count={cnt}")
            if cnt > 0:
                sess = conn.Children(0)
                log(f"  session OK: {sess} Type={getattr(sess,'Type','?')}")
                break
        except Exception as e:
            log(f"  wait {i+1}s: Children ERR {type(e).__name__}")

except Exception as e:
    log(f"TOP ERR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
