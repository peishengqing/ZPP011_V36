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
