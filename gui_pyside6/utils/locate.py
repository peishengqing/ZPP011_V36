# -*- coding: utf-8 -*-
"""看板行定位：双击看板任意行 → 选中主表对应行。

历史背景：4 个看板此前调用 ``main_window.locate_record(...)``，但该方法在
main_window 中从未实现，异常又被 ``except (AttributeError, Exception): pass``
吞掉，导致「双击定位主表」静默失效（P0）。此处统一为一条可靠链路。

定位优先级（可靠性从高到低）：
1. 「原表行号」列值精确匹配 —— 不受筛选/排序/索引类型影响；
2. ``data_id`` 匹配 —— 由 工厂|订单日期|物料编码 组合，排序后仍稳定；
3. DataFrame 索引标签匹配 —— 兼容旧 ``_locate_row_by_index`` 语义。

三条都失败时给出明确提示，不再静默。
"""
from gui_pyside6.widgets.toast import toast


def _cell_text(record, key):
    """从 Series/映射里取一个可用的字符串值，空值返回 None。"""
    try:
        value = record.get(key)
    except Exception:
        return None
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in ("nan", "none", "nat"):
        return None
    return text


def _try(main_window, method_name, arg, silent=False):
    finder = getattr(main_window, method_name, None)
    if not callable(finder):
        return False
    try:
        if method_name == "_locate_row_in_main_table":
            return bool(finder(arg, silent=silent))
        return bool(finder(arg))
    except TypeError:
        return False
    except Exception:
        return False


def locate_row(main_window, record, parent=None, link_source=""):
    """把看板某行定位到主表并选中；成功返回 True。"""
    """link_source 非空时，定位成功后主表联动钻取到该记录所在订单上下文（可撤销）。"""
    if main_window is None or record is None:
        return False

    excel_no = _cell_text(record, "原表行号")
    data_id = _cell_text(record, "data_id")
    ok = False
    if excel_no is not None and _try(main_window, "_locate_row_by_excel_no", excel_no):
        ok = True
    elif data_id is not None and _try(main_window, "_locate_row_in_main_table", data_id, silent=True):
        ok = True
    elif excel_no is not None and _try(main_window, "_locate_row_by_index", excel_no):
        ok = True

    if ok and link_source:
        # v43.153：联动钻取失败不影响「选中行」本身，但绝不能再静默——
        # 旧版 except Exception: pass 把 _apply_link_drilldown 里的 KeyError 完全吞掉，
        # 用户看到的现象是「会跳转到主表、但主表不筛选、也没有联动横幅」，
        # 现场零线索，排查只能靠猜。现在打日志 + 弹可见提示。
        try:
            main_window._apply_link_drilldown(record, link_source)
        except Exception:
            import traceback
            traceback.print_exc()
            try:
                main_window.log(
                    "[联动钻取] 失败: %s" % traceback.format_exc(limit=3), "warning")
            except Exception:
                pass
            toast("已定位到该行，但联动筛选未生效（详情见日志）",
                  level="warning", parent=parent)
    elif not ok:
        toast("未在主表中找到该记录（可能已被筛选或隔离）", level="warning", parent=parent)

    return ok


def drill_to_workshop(main_window, record, link_source=""):
    """右键「下钻该车间」：主表按 工厂+车间 聚焦（可撤销，复用联动横幅机制）。

    record 为看板行 pandas Series。各看板工厂字段名不统一：
    负损/正损用「工厂名称」，偏差率/替代料用「工厂」，半成品无工厂列 → 工厂留空仅按车间筛。

    v43.329：返回 bool（是否成功聚焦）。看板是模态 exec()，成功后由调用方
    accept() 自行关闭，否则主表虽已筛选却被看板窗口挡住，用户以为「没反应」。
    失败时给可见 toast，不再静默 return。
    """
    if main_window is None or record is None:
        return False
    try:
        ws = record.get("车间")
        if ws is None:
            toast("该行没有「车间」列，无法下钻", level="warning", parent=main_window)
            return False
        ws = str(ws).strip()
        if not ws or ws.lower() in ("nan", "none"):
            toast("该行车间为空，无法下钻", level="warning", parent=main_window)
            return False
        fac = record.get("工厂名称")
        if fac is None or str(fac).strip() in ("", "nan", "none"):
            fac = record.get("工厂")
        fac = str(fac).strip() if fac is not None else ""
        fn = getattr(main_window, "_filter_main_table_to_workshop", None)
        if not callable(fn):
            toast("主表不支持车间下钻", level="warning", parent=main_window)
            return False
        return bool(fn(fac, ws, link_source or "看板"))
    except Exception:
        import traceback
        traceback.print_exc()
        try:
            toast("车间下钻失败（详情见日志）", level="warning", parent=main_window)
        except Exception:
            pass
        return False


def compute_mom_badge(df):
    """从看板 df 的「订单日期」派生本期期段与环比角标文本。
    返回 (period_text, badge_text, has_prev)。
    仅单月/无订单日期 → has_prev=False，badge 灰显「无上期」。
    """
    import pandas as pd
    if df is None or "订单日期" not in df.columns or len(df) == 0:
        return "", "环比：无数据", False
    try:
        s = pd.to_datetime(df["订单日期"], errors="coerce")
    except Exception:
        return "", "环比：无数据", False
    s = s.dropna()
    if s.empty:
        return "", "环比：无数据", False
    months = s.dt.to_period("M")
    cur = months.max()
    prev = months[months < cur]
    period_text = "%s ~ %s" % (s.min().strftime("%Y-%m-%d"), s.max().strftime("%Y-%m-%d"))
    if prev.empty:
        return period_text, "环比：无上期", False
    cur_n = int((months == cur).sum())
    prev_n = int((months == prev.max()).sum())
    if prev_n == 0:
        return period_text, "环比：无上期", False
    diff = cur_n - prev_n
    pct = diff / prev_n * 100.0
    arrow = "↑" if diff > 0 else ("↓" if diff < 0 else "→")
    badge = "环比 %s%d 条 (%+.1f%%)" % (arrow, diff, pct)
    return period_text, badge, True
