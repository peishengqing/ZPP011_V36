"""探测 SAP GUI 8.0 多种引擎获取方式。"""
import time
import win32com.client

def log(msg): print(f"[PROBE] {msg}", flush=True)

def try_get(label, factory):
    try:
        obj = factory()
        log(f"{label} OK -> {obj}")
        for attr in ['Type', 'Children', 'Connections', 'Sessions', 'Name']:
            try:
                v = getattr(obj, attr)
                if hasattr(v, 'Count'):
                    log(f"  {label}.{attr}.Count = {v.Count}")
                else:
                    log(f"  {label}.{attr} = {v}")
            except Exception as e:
                log(f"  {label}.{attr} ERR: {type(e).__name__}")
        return obj
    except Exception as e:
        log(f"{label} FAIL: {type(e).__name__}: {e}")
        return None

# 各种可能的 ProgID / 取对象方式
engine = None
engine = try_get("GetObject('SAPGUI')", lambda: win32com.client.GetObject("SAPGUI"))
if engine is None:
    engine = try_get("Dispatch('SAPGUI')", lambda: win32com.client.Dispatch("SAPGUI"))
if engine is None:
    engine = try_get("Dispatch('SapGui.Application')", lambda: win32com.client.Dispatch("SapGui.Application"))
if engine is None:
    engine = try_get("Dispatch('SapGui.ScriptingCtrl.1')", lambda: win32com.client.Dispatch("SapGui.ScriptingCtrl.1"))

if engine is None:
    log("所有方式都失败，无法继续")
    sys.exit(1)

# 如果有 Children，显示连接
if hasattr(engine, 'Children'):
    for i in range(engine.Children.Count):
        c = engine.Children(i)
        log(f"  conn[{i}] Id={getattr(c,'Id','?')} Desc={getattr(c,'Description','?')}")

# 尝试 OpenConnection
log("\n尝试 OpenConnection('PS4') ...")
try:
    conn = engine.OpenConnection("PS4")
    log(f"OpenConnection OK: {conn}")
    for i in range(20):
        time.sleep(1)
        try:
            cnt = conn.Children.Count
            log(f"  wait {i+1}s: Children.Count={cnt}")
            if cnt > 0: break
        except Exception as e:
            log(f"  wait {i+1}s: Children ERR {type(e).__name__}")
except Exception as e:
    log(f"OpenConnection FAIL: {type(e).__name__}: {e}")
