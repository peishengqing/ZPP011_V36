# -*- coding: utf-8 -*-
"""第三期弹窗规范门禁（设计稿 v43.333 dialogs.html 的「外壳一~四」）。

为什么要有这些测试
------------------
改造前 30+ 弹窗的尺寸、标题、按钮写法各写各的：同类弹窗大小差一倍、标题一半带
emoji（部分 Windows 字体渲染成方块）、确认框统一「是 / 否」按下去不知道会发生什么、
错误框只有一句 str(e) 截图反馈也看不全。这类「规范」问题靠人眼 review 守不住，
只能写成断言：改回去立刻红。

六道门禁
--------
1. 静态扫描：所有 ``dialog_chrome.apply(...)`` / ``setWindowTitle(...)`` 的字面量里
   不允许出现 emoji（标题只写「名称 · 副标」）。
2. 静态扫描：dialogs/ 下每个 QDialog 都必须套尺寸档；白名单只许缩短（第四期规则中心、
   待删的看板副本除外，新增一个就红）。
3. ``apply()`` 行为：标题格式、尺寸等于 ``tokens.DIALOG_SIZES``、只有 large/board
   给最大化按钮、未知档位抛 KeyError。
4. 外壳组件（VerdictBanner / ImpactBanner / StepChain / style_with_tokens）：
   颜色只能来自 TOKENS、亮暗切换要重刷、控件销毁后回调必须摘掉（否则每开一次弹窗
   就往 Thm 的全局列表里漏一只）。
5. ``message_box`` 行为：按钮写动作、confirm 只有主动作返回 True、错误框「复制详情」
   真的把「标题 + 技术详情」写进剪贴板。
6. 迁移落地：已迁移文件里彻底不再出现 QMessageBox；破坏性确认必须走 danger 分支。
"""
import ast
import io
import os
import re
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from gui_pyside6.components import dialog_chrome, message_box  # noqa: E402
from gui_pyside6.themes.tokens import DIALOG_SIZES, TOKENS  # noqa: E402
from utils.theme_manager import Thm  # noqa: E402

DIALOG_DIR = os.path.join(ROOT, "gui_pyside6", "dialogs")

#: 图形 emoji / 装饰符号区（含变体选择符）：这些字符出现在标题里就是设计稿说的「方块」风险。
#: 只盯「 pictographs / dingbats / 杂项符号 + 变体选择符」，故意放行 ``→ ≥``（U+2190-22FF
#: 的箭头与数学符号在 Windows 字体里从来不会渲染成方块，而「选表 → 列映射 → 确认」
#: 「|偏差率| ≥ 10%」这类副标正是设计稿要的信息）。
EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE00-\uFE0F\u200D]")

#: 还没套尺寸档的弹窗白名单（只许缩短，不许变长）
APPLY_TODO = {
    # 待删副本：无活跃调用方，删文件时这一项自然消失
    "neg_loss_dashboard_dialog.py",
    "pos_loss_dashboard_dialog.py",
    "semi_dashboard_dialog.py",
}

#: 已经完全改用 message_box 模板的文件（门禁 6：这些文件里 QMessageBox 必须为 0）
MIGRATED = [
    "gui_pyside6/controllers/export_controller.py",
    "gui_pyside6/controllers/ppt_controller.py",
    "gui_pyside6/controllers/semi_category_controller.py",
    "gui_pyside6/dialogs/auto_read_rule_dialog.py",
    "gui_pyside6/dialogs/filter_preset_manager_dialog.py",
    "gui_pyside6/dialogs/threshold_config_dialog.py",
    "gui_pyside6/dialogs/wechat_draft_config_dialog.py",
]


def _read(rel):
    with io.open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def _dialog_sources():
    for fn in sorted(os.listdir(DIALOG_DIR)):
        if fn.endswith(".py") and fn != "__init__.py":
            with io.open(os.path.join(DIALOG_DIR, fn), encoding="utf-8") as f:
                yield fn, f.read()


def _string_args_of_apply(src):
    """AST 取出 dialog_chrome.apply(...) 里所有字符串字面量参数。"""
    out = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "apply"
                and isinstance(fn.value, ast.Name)
                and fn.value.id == "dialog_chrome"):
            continue
        for arg in node.args[1:]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                out.append(arg.value)
    return out


# ---------------------------------------------------------------- 门禁 1
@pytest.mark.parametrize("fn", [fn for fn, _ in _dialog_sources()])
def test_dialog_titles_have_no_emoji(fn):
    src = _read(os.path.join("gui_pyside6", "dialogs", fn))
    bad = [t for t in _string_args_of_apply(src) if EMOJI_RE.search(t or "")]
    # 标题字面量 + 直接 setWindowTitle 的字面量一起查
    for m in re.finditer(r'setWindowTitle\(\s*"([^"]*)"', src):
        if EMOJI_RE.search(m.group(1)):
            bad.append(m.group(1))
    assert not bad, "%s 的标题里还有 emoji：%s（设计稿：标题只写「名称 · 副标」）" % (fn, bad)


# ---------------------------------------------------------------- 门禁 2
def test_every_dialog_has_a_size_tier():
    missing = []
    for fn, src in _dialog_sources():
        tree = ast.parse(src)
        is_dialog = any(
            isinstance(n, ast.ClassDef) and any(
                isinstance(b, ast.Name) and b.id in ("QDialog", "QWizard")
                for b in n.bases)
            for n in ast.walk(tree))
        if is_dialog and "dialog_chrome.apply(" not in src:
            missing.append(fn)
    extra = sorted(set(missing) - APPLY_TODO)
    assert not extra, "这些弹窗没套尺寸档，请调用 dialog_chrome.apply()：%s" % extra


# ---------------------------------------------------------------- 门禁 3
def test_apply_sets_title_size_and_flags(qapp):
    from PySide6.QtWidgets import QDialog
    from PySide6.QtCore import Qt

    d = QDialog()
    dialog_chrome.apply(d, dialog_chrome.TIER_SMALL, "物料速查", "按编码看当前值")
    assert d.windowTitle() == "物料速查 · 按编码看当前值"
    assert (d.width(), d.height()) == DIALOG_SIZES["small"]
    flags = d.windowFlags()
    assert not flags & Qt.WindowMaximizeButtonHint, "小表单不该给最大化"
    assert not flags & Qt.WindowMinimizeButtonHint, "标题栏留个没用的箭头更误导"

    big = QDialog()
    dialog_chrome.apply(big, dialog_chrome.TIER_LARGE, "审核证据卡")
    assert big.windowTitle() == "审核证据卡"
    assert (big.width(), big.height()) == DIALOG_SIZES["large"]
    assert big.windowFlags() & Qt.WindowMaximizeButtonHint, "内容会超一屏才给最大化"


def test_apply_rejects_unknown_tier(qapp):
    from PySide6.QtWidgets import QDialog
    with pytest.raises(KeyError):
        dialog_chrome.apply(QDialog(), "huge", "名字")


def test_format_title_strips_decorations():
    assert dialog_chrome.format_title("⚙ 规则中心") == "规则中心"
    assert dialog_chrome.format_title("🪪 物料画像", "100327825") == "物料画像 · 100327825"
    # 非字符串（int data_id）也要能吃，历史上这里 TypeError 过一次
    assert dialog_chrome.format_title("数据稳定性", 20250907) == "数据稳定性 · 20250907"


# ---------------------------------------------------------------- 门禁 4
def _token_hexes(theme):
    return {v.lower() for v in TOKENS[theme].values() if isinstance(v, str)}


@pytest.mark.parametrize("tone", ["ok", "danger", "warn", "info"])
def test_verdict_banner_colors_come_from_tokens(qapp, tone):
    b = dialog_chrome.VerdictBanner("结论：可以放行", "置信度：高", tone)
    css = b.styleSheet()
    assert "#" in css
    off = [h for h in re.findall(r"#[0-9A-Fa-f]{6}", css)
           if h.lower() not in _token_hexes("light")]
    assert not off, "结论条出现表外色号 %s" % off


def test_verdict_banner_restyled_on_theme_flip(qapp):
    b = dialog_chrome.VerdictBanner("结论", "", "info")
    light_css = b.styleSheet()
    Thm.set_dark(True)
    try:
        assert b.styleSheet() != light_css, "暗色下结论条没重刷（回调签名不匹配时 Thm 会把报错吞掉）"
    finally:
        Thm.set_dark(False)
    assert light_css == b.styleSheet()


def test_destroyed_widget_unregisters_theme_callback(qapp):
    from PySide6.QtWidgets import QLabel
    from PySide6.QtCore import QEvent
    before = len(Thm._callbacks)
    lbl = QLabel("x")
    cb = dialog_chrome.style_with_tokens(lbl, "QLabel { color:$textMuted; }")
    assert len(Thm._callbacks) == before + 1
    lbl.deleteLater()
    qapp.processEvents()
    # processEvents 不冲洗 DeferredDelete（探针实测：只 processEvents 时 destroyed
    # 根本不触发），必须显式 sendPostedEvents 才会真正销毁 C++ 对象。
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()
    assert cb not in Thm._callbacks, "控件销毁后回调没摘掉 → 每次开弹窗漏一只"


def test_style_with_tokens_substitutes_every_token(qapp):
    from PySide6.QtWidgets import QLabel
    lbl = QLabel("x")
    dialog_chrome.style_with_tokens(
        lbl, "QPushButton#p { background:$primary; color:$onPrimary; }"
             " QLabel { color:$textMuted; }")
    css = lbl.styleSheet()
    assert "$" not in css, "还有没替换掉的令牌占位：%s" % css
    tk = TOKENS["light"]
    assert tk["primary"] in css and tk["onPrimary"] in css and tk["textMuted"] in css


def test_step_chain_numbers_its_items(qapp):
    from PySide6.QtWidgets import QLabel
    chain = dialog_chrome.StepChain(["规则版本 v12", "模型版本 agnes-3.0-flash", "生成时间 09:40"])
    nums = [l.text() for l in chain.findChildren(QLabel) if l.objectName() == "chainStepNo"]
    assert nums == ["1", "2", "3"]


def test_impact_banner_rewrites_text(qapp):
    b = dialog_chrome.ImpactBanner("将影响 <b>3</b> 行")
    b.set_text("将影响 <b>5</b> 行")
    assert b.lbl.text() == "将影响 <b>5</b> 行"


# ---------------------------------------------------------------- 门禁 5
@pytest.fixture
def clicker(monkeypatch):
    """把 ``QMessageBox.exec`` 换成「点指定按钮」。

    按钮得先可见：``QAbstractButton.click()`` 对隐藏控件不发射信号，直接点会静默
    失败、测试拿到 None。offscreen 平台下 show() 不会真开窗。
    """
    from PySide6.QtWidgets import QMessageBox

    holder = {"label": None}

    def _exec(self):
        self.show()
        try:
            for btn in self.buttons():
                if btn.text().replace("&", "") == holder["label"]:
                    btn.click()
                    return 0
            raise AssertionError("弹窗里没有按钮 %r，实有：%s"
                                 % (holder["label"], [b.text() for b in self.buttons()]))
        finally:
            self.hide()

    monkeypatch.setattr(QMessageBox, "exec", _exec)
    return holder


def test_confirm_yes_no(qapp, clicker):
    clicker["label"] = "删除预设"
    assert message_box.confirm(None, "要删除预设「A」吗", "删掉就选不到了",
                               yes="删除预设", no="先不删") is True
    clicker["label"] = "先不删"
    assert message_box.confirm(None, "要删除预设「A」吗", "删掉就选不到了",
                               yes="删除预设", no="先不删") is False


def test_info_and_warn_have_one_leave_button(qapp, clicker):
    clicker["label"] = message_box.OK
    assert message_box.info(None, "配置已保存", "下次生成就用这套字段") == message_box.OK
    clicker["label"] = message_box.OK
    assert message_box.warn(None, "表格里没有数据", "先跑一次分析") == message_box.OK


def test_ask_returns_clicked_label(qapp, clicker):
    clicker["label"] = "存为副本"
    got = message_box.ask(None, "保存不了", "文件被 Excel 占着",
                          labels=["重试", "存为副本", "取消"])
    assert got == "存为副本"


def test_error_copies_technical_detail_to_clipboard(qapp, clicker):
    from PySide6.QtWidgets import QApplication
    try:
        raise ValueError("列 偏差数量 不存在")
    except ValueError as e:
        clicker["label"] = "复制详情"
        message_box.error(None, "导出没成功", "表里的数据没有改动。",
                          exc=e, detail="E:\\out.xlsx")
    text = QApplication.clipboard().text()
    assert "导出没成功" in text
    assert "ValueError" in text and "列 偏差数量 不存在" in text
    assert "out.xlsx" in text


# ---------------------------------------------------------------- 门禁 6
@pytest.mark.parametrize("rel", MIGRATED)
def test_migrated_files_do_not_use_qmessagebox_anymore(rel):
    # 只查属性访问（QMessageBox.xxx）：文档字符串里提一句「以前用 QMessageBox」不算残留
    hits = [ln.strip() for ln in _read(rel).splitlines() if "QMessageBox." in ln]
    assert not hits, "%s 仍在直接用 QMessageBox（应统一 message_box 模板）：%s" % (rel, hits)


def test_semi_reset_only_wipes_after_confirmation(qapp):
    """重置半成品分类：点「先不清空」必须什么都不能删。

    历史 bug：旧代码写成 ``if not QMessageBox.question(...) == QMessageBox.No``，
    运算符优先级让它变成 ``not (question == No)``，于是用户点「否」反而清空了分类。
    """
    from unittest import mock
    from PySide6.QtWidgets import QWidget
    from gui_pyside6.controllers.semi_category_controller import SemiCategoryController

    mw = QWidget()
    mw._semi_categories = {"400001": "彩罐", "410001": "托盘"}
    ctrl = SemiCategoryController(mw)
    for name in ("_save_semi_categories", "_refresh_semi_list_ui"):
        setattr(mw, name, mock.Mock())

    with mock.patch("gui_pyside6.components.message_box.confirm",
                    return_value=False) as cfm:
        ctrl._reset_semi_categories()
    assert mw._semi_categories, "用户点「先不清空」却把分类清了"
    assert cfm.call_count == 1
    kwargs = cfm.call_args.kwargs
    assert kwargs.get("danger") is True, "破坏性操作要走 DestructiveRole"
    assert kwargs.get("yes") == "清空重建" and kwargs.get("no") == "先不清空", \
        "按钮仍写「是 / 否」：%s / %s" % (kwargs.get("yes"), kwargs.get("no"))

    with mock.patch("gui_pyside6.components.message_box.confirm", return_value=True), \
            mock.patch("gui_pyside6.components.message_box.info") as info:
        ctrl._reset_semi_categories()
    assert mw._semi_categories == {}, "用户确认后应当清空分类"
    assert info.call_count == 1, "清空成功后要有一句人话回执"
