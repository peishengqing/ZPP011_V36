# -*- coding: utf-8 -*-
"""
ZPP011 - SAP GUI 自动拉取脚本（SAP GUI Scripting）

功能：
    通过本机已安装的 SAP GUI 客户端（Scripting 模式），自动登录指定连接、
    执行 ZPP011 报表事务码、把结果导出为本地 Excel，供 ZPP011 审计工具直接导入。

依赖：
    - 本机安装 SAP GUI（已验证 C:\Program Files\SAP\FrontEnd\SAPgui\sapfewse.ocx 存在）
    - Python 包 pywin32（已 pip install pywin32）
    - SAP GUI 客户端需开启"脚本支持"（选项→辅助功能→启用脚本，取消"通知用户脚本正在运行"）

配置：
    - tools/sap_pull_config.json   非敏感配置（连接名/客户端/用户/事务码/导出目录）
    - tools/sap_pull_secret.json  密码（已被 .gitignore 忽略，切勿提交）
      也可通过环境变量 SAP_PULL_PASSWORD 传入，优先级高于 secret 文件

模式：
    --explore      只读：登录 -> 进入 ZPP011 选择屏幕 -> 打印真实字段 ID 与工具栏按钮，
                   用于校准 selection 字段与导出菜单 ID。不做任何写操作。
    --pull         自动拉取：登录 -> 进 ZPP011 -> 填日期 -> 执行 -> 导出 Excel 到 out_dir。
                   （导出菜单 ID 需先用 --explore 拿到真实结构后校准 run_report()）

运行：
    python tools/sap_pull.py --explore
    python tools/sap_pull.py --pull --date-from 2026-07-01 --date-to 2026-07-10
"""

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
CONFIG_PATH = os.path.join(HERE, "sap_pull_config.json")
SECRET_PATH = os.path.join(HERE, "sap_pull_secret.json")
DEFAULT_OUT_DIR = r"E:\ZPP011导出文件原数据"

# 标准 SAP 登录屏字段 ID（很稳定，各系统基本一致）
LOGIN = {
    "client": "wnd[0]/usr/txtRSYST-MANDT",
    "user": "wnd[0]/usr/txtRSYST-BNAME",
    "password": "wnd[0]/usr/txtRSYST-BCODE",
    "language": "wnd[0]/usr/txtRSYST-LANGU",
}


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"读取配置失败: {e}")
        return {}


def get_password():
    env = os.environ.get("SAP_PULL_PASSWORD")
    if env:
        return env
    if os.path.exists(SECRET_PATH):
        try:
            with open(SECRET_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("password", "")
        except Exception:
            return ""
    return ""


def get_scripting_engine():
    import win32com.client
    try:
        gui = win32com.client.GetObject("SAPGUI")
        log("已连接到正在运行的 SAP GUI")
    except Exception:
        gui = win32com.client.Dispatch("SapGui.ScriptingCtrl.1")
        log("SAP GUI 未运行，已创建脚本控件")
    return gui.GetScriptingEngine


def find_logged_connection(engine, conn_name):
    """在已打开连接中找匹配 conn_name 且已登录的。"""
    cons = engine.Children
    for i in range(cons.Count):
        conn = cons(i)
        try:
            if conn_name and conn_name.lower() not in (conn.Description or "").lower():
                continue
        except Exception:
            pass
        sessions = conn.Children
        for j in range(sessions.Count):
            ses = sessions(j)
            try:
                if ses.Info.IsAvailable and ses.Info.Type == "MainWindow" and ses.Info.Transaction:
                    return ses
            except Exception:
                continue
    return None


def login(engine, cfg, password):
    """登录到指定连接，返回已登录的 session。复用已登录的，否则新建。"""
    conn_name = cfg.get("connection_name", "")
    client = cfg.get("client", "")
    user = cfg.get("user", "")
    lang = cfg.get("language", "ZH")

    reused = find_logged_connection(engine, conn_name)
    if reused is not None:
        log(f"复用已登录连接: {conn_name}")
        return reused

    log(f"打开连接 {conn_name} ...")
    conn = engine.OpenConnection(conn_name)
    session = None
    for _ in range(60):
        try:
            cnt = conn.Children.Count
            if cnt > 0:
                session = conn.Children(0)
                break
            if _ % 10 == 0:
                log(f"  等待会话窗口... Children.Count={cnt}")
        except Exception as e:
            if _ % 10 == 0:
                log(f"  读取 Children 异常: {type(e).__name__}")
        time.sleep(0.5)
    if session is None:
        raise RuntimeError("打开连接后 30s 内未出现会话窗口")
    time.sleep(2.0)

    log("填写登录信息 ...")
    session.FindById(LOGIN["client"]).Text = client
    session.FindById(LOGIN["user"]).Text = user
    session.FindById(LOGIN["password"]).Text = password
    try:
        session.FindById(LOGIN["language"]).Text = lang
    except Exception:
        pass
    session.FindById("wnd[0]").SendVKey(0)  # Enter 登录
    time.sleep(3.0)
    log("登录请求已发送，等待主屏幕 ...")
    return conn.Children(0)


def explore_selection_screen(session, tcode):
    """只读：进入事务码选择屏幕，打印所有字段与工具栏按钮 ID。"""
    log(f"进入事务码 {tcode}（只读探查）...")
    try:
        session.StartTransaction(tcode)
    except Exception as e:
        log(f"StartTransaction 失败（可能无权限或事务码不存在）: {e}")
        return
    time.sleep(2.0)

    try:
        cur = session.Info.Transaction
        log(f"当前事务码: {cur}")
    except Exception:
        pass

    log("=== 选择屏幕输入字段（usr 容器） ===")
    try:
        usr = session.FindById("wnd[0]/usr")
        for i in range(usr.Children.Count):
            c = usr.Children(i)
            try:
                cid = c.ID
                ctype = c.Type
                ctext = getattr(c, "Text", "") or ""
                label = ""
                try:
                    label = c.FindById("lblField") if False else ""
                except Exception:
                    label = ""
                log(f"  {cid}  type={ctype}  text={ctext!r}")
            except Exception as e:
                log(f"  child[{i}] 读取失败: {e}")
    except Exception as e:
        log(f"读取 usr 容器失败: {e}")

    log("=== 标准工具栏按钮（tbar[1]，含导出图标 btn[45]） ===")
    try:
        tbar = session.FindById("wnd[0]/tbar[1]")
        for i in range(tbar.Children.Count):
            b = tbar.Children(i)
            try:
                log(f"  btn[{i}] id={b.ID} tooltip={getattr(b, 'ToolTip', '')!r}")
            except Exception:
                pass
    except Exception as e:
        log(f"读取工具栏失败: {e}")

    log("（探查完成，未执行/未导出。把上面的字段 ID 用于校准 sap_pull_config.json 的 selection）")


def run_report(session, cfg, date_from="", date_to=""):
    """执行报表并导出 Excel。导出菜单 ID 需先用 --explore 校准。"""
    tcode = cfg.get("tcode", "")
    if not tcode:
        raise RuntimeError("配置缺少 tcode")
    sel = cfg.get("selection", {})
    out_dir = cfg.get("out_dir", DEFAULT_OUT_DIR)
    os.makedirs(out_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(out_dir, f"ZPP011_SAP_{stamp}.xlsx")

    log(f"执行事务码 {tcode} ...")
    session.StartTransaction(tcode)
    time.sleep(1.5)

    if date_from and sel.get("date_from_id"):
        session.FindById(sel["date_from_id"]).Text = date_from
        log(f"填起始日期 {date_from}")
    if date_to and sel.get("date_to_id"):
        session.FindById(sel["date_to_id"]).Text = date_to
        log(f"填截止日期 {date_to}")

    if sel.get("execute_btn_id"):
        session.FindById(sel["execute_btn_id"]).Press()
    else:
        session.SendVKey(8)
    time.sleep(2.0)

    # ---- 导出为本地 Excel（电子表格）----
    try:
        session.FindById("wnd[0]/tbar[1]/btn[45]").Press()          # 导出图标
        session.FindById("menu[0]/menu[1]/menu[2]").Select()        # 电子表格
        session.FindById("wnd[1]/usr/ctxtDY_PATH").Text = out_dir
        session.FindById("wnd[1]/usr/ctxtDY_FILENAME").Text = os.path.basename(out_file)
        session.FindById("wnd[1]/tbar[0]/btn[11]").Press()          # 保存
        log(f"已导出到: {out_file}")
        return out_file
    except Exception as e:
        log(f"导出失败（导出菜单 ID 可能与你的 SAP 版本不符，请先用 --explore 校准）: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="ZPP011 SAP GUI 自动拉取")
    parser.add_argument("--explore", action="store_true",
                        help="只读探查 ZPP011 选择屏幕字段（校准用）")
    parser.add_argument("--pull", action="store_true",
                        help="执行报表并导出 Excel")
    parser.add_argument("--date-from", default="", help="选择屏幕起始日期 YYYYMMDD")
    parser.add_argument("--date-to", default="", help="选择屏幕截止日期 YYYYMMDD")
    args = parser.parse_args()

    cfg = load_config()
    if not cfg.get("connection_name") or not cfg.get("tcode"):
        log("配置缺少 connection_name / tcode，请先填写 tools/sap_pull_config.json")
        sys.exit(1)

    password = get_password()
    if not password:
        log("未找到密码：请设置环境变量 SAP_PULL_PASSWORD 或填写 tools/sap_pull_secret.json")
        sys.exit(1)

    engine = get_scripting_engine()
    session = login(engine, cfg, password)

    if args.explore:
        explore_selection_screen(session, cfg.get("tcode", ""))
        return

    if args.pull:
        out = run_report(session, cfg, args.date_from, args.date_to)
        if out:
            log(f"完成。Excel: {out}")
        else:
            log("拉取未完成，请用 --explore 校准字段/导出 ID")
        return

    log("未指定 --explore / --pull。仅完成登录验证。")


if __name__ == "__main__":
    main()
