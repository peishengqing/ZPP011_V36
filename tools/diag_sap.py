import win32com.client, time

def log(m):
    print(m, flush=True)

gui = win32com.client.GetObject("SAPGUI")
engine = gui.GetScriptingEngine()
log("engine repr: %r" % repr(engine))
time.sleep(2)

for a in ("Connections", "Children"):
    try:
        obj = getattr(engine, a)
        log("engine.%s -> Count=%s" % (a, obj.Count))
    except Exception as e:
        log("engine.%s ERR: %r" % (a, e))

log("OpenConnection PS4 ...")
try:
    conn = engine.OpenConnection("PS4")
    log("conn repr: %r" % repr(conn))
except Exception as e:
    log("OpenConnection ERR: %r" % e)
    conn = None

if conn is not None:
    for t in range(45):
        cc = ss = "?"
        try:
            cc = conn.Children.Count
        except Exception as e:
            cc = "err:%r" % e
        try:
            ss = conn.Sessions.Count
        except Exception as e:
            ss = "err:%r" % e
        log("  t=%d Children=%s Sessions=%s" % (t, cc, ss))
        if (isinstance(cc, int) and cc > 0) or (isinstance(ss, int) and ss > 0):
            log("  >>> 会话出现")
            # 打印会话类型
            try:
                for k in range(conn.Children.Count):
                    s = conn.Children(k)
                    log("    sess[%d] Type=%s Id=%s" % (k, s.Type, s.Id))
            except Exception as e:
                log("    sess detail err: %r" % e)
            break
        time.sleep(1)
log("done")
