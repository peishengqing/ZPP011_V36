"""深度诊断 SAP GUI 连接与会话状态。"""
import sys
import time
import win32com.client

def log(msg): print(f"[DIAG] {msg}", flush=True)

def safe_attr(obj, attr, default="(error)"):
    try: return getattr(obj, attr)
    except Exception as e: return f"{default}: {type(e).__name__}"

try:
    engine = win32com.client.GetObject("SAPGUI")
    log(f"GetObject OK: {engine}")
except Exception as e:
    log(f"GetObject 失败: {type(e).__name__}: {e}")
    engine = win32com.client.Dispatch("SapGui.ScriptingCtrl.1")
    log(f"Dispatch OK: {engine}")

log(f"engine.Type = {safe_attr(engine, 'Type')}")
log(f"engine.Children.Count = {safe_attr(engine, 'Children', '(no Children)')}")

def dump_conn(c, name):
    log(f"--- {name} ---")
    log(f"  Type = {safe_attr(c, 'Type')}")
    log(f"  Id = {safe_attr(c, 'Id')}")
    log(f"  Description = {safe_attr(c, 'Description')}")
    log(f"  Children.Count = {safe_attr(c, 'Children', '(no Children)')}")
    log(f"  Sessions.Count = {safe_attr(c, 'Sessions', '(no Sessions)')}")
    log(f"  IsConnected = {safe_attr(c, 'IsConnected', '(no IsConnected)')}")

for i in range(engine.Children.Count):
    c = engine.Children.Item(i)
    dump_conn(c, f"existing conn[{i}]")

log("\n尝试 OpenConnection('PS4') ...")
new_conn = engine.OpenConnection("PS4")
log(f"new_conn = {new_conn}")
log(f"  new_conn.Type = {safe_attr(new_conn, 'Type')}")
log(f"  new_conn.Id = {safe_attr(new_conn, 'Id')}")
log(f"  new_conn.Children.Count = {safe_attr(new_conn, 'Children', '(no Children)')}")
log(f"  new_conn.Sessions.Count = {safe_attr(new_conn, 'Sessions', '(no Sessions)')}")
log(f"  new_conn.IsConnected = {safe_attr(new_conn, 'IsConnected', '(no IsConnected)')}")

for i in range(10):
    time.sleep(1)
    log(f"  wait {i+1}s: Children={safe_attr(new_conn, 'Children', '(no Children)')}, Sessions={safe_attr(new_conn, 'Sessions', '(no Sessions)')}")

log("\nOpenConnection 后 engine.Children:")
for i in range(engine.Children.Count):
    c = engine.Children.Item(i)
    dump_conn(c, f"conn[{i}] after OpenConnection")
