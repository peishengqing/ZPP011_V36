# -*- coding: utf-8 -*-
"""设计令牌防漂移门禁（设计稿 v43.333 第一期第 1 条的机器化验收）。

为什么要这个测试
----------------
改造前全仓有 5 份各自写死的颜色真源，同一个「主色」存在 4 个值（#1E40AF /
#4C7DFF / #0969DA / #5C7CFA），改一套漏两套 → 裴哥的原始反馈就是
「看板和你做的界面两处不太像一个产品的」。这类问题靠人眼 grep 守不住，
只能把「颜色必须等于令牌取值」写成断言，改错立刻红。

四条门禁
--------
1. 运行时两套 app QSS（light_theme.qss / dark_theme.qss）里出现的**每一个色号**
   必须是本主题令牌表的取值 —— 写一个表外颜色就失败。
2. themes/{light,dark}_dashboard.qss 必须与 tokens.build_dashboard_qss()
   逐字节一致（它们是构建产物，不再手写）。
3. 生成器里不允许出现表外圆角 / 字号（圆角只允许 4/6/10 + 胶囊 18，
   字号只允许 FONT_PT 档位）。
4. ``gui_pyside6/**/*.py`` 的**字符串常量**（QSS 内联样式、QColor、HTML 富文本）
   里不允许出现表外色号；旧主色（#0969DA/#5C7CFA/#0078D4/#7F77DD/#6B63D5）
   更是零容忍。历史遗留点位用 DEFERRED 记名挂账（见下），只许减少不许增加。

DEFERRED 挂账规则
-----------------
字典里的每一项 = 「这个文件还有几处表外色号」，并标注由哪一期收口。
- 新增点位 → 数量超预算，测试红；
- 按期清掉 → 必须同步把数字改小（数量低于预算同样失败），防止挂账腐烂。
"""
import ast
import io
import os
import re
import sys
import warnings

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from gui_pyside6.themes.tokens import (  # noqa: E402
    FONT_PT, SIZE_PX, TOKENS, build_board_qss, build_dashboard_qss,
)

HEX_RE = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
RADIUS_RE = re.compile(r"border-radius:\s*([0-9]+)px")
FONT_SIZE_RE = re.compile(r"font-size:\s*([0-9]+)px")

#: 旧主色（改造前 5 份真源留下的值），代码里一律禁止
LEGACY_PRIMARY = {"#0969da", "#5c7cfa", "#0078d4", "#7f77dd", "#6b63d5"}

#: 允许出现在 QSS 里的圆角档位（SIZE_PX 的 4 个半径键 + 0）
ALLOWED_RADIUS = {0, SIZE_PX["radiusSm"], SIZE_PX["radiusMd"],
                  SIZE_PX["radiusLg"], SIZE_PX["radiusPill"]}
#: 允许出现在 QSS 里的字号档位（FONT_PT 值集）
ALLOWED_FONT_PX = set(FONT_PT.values())

#: 挂账：文件 → 允许的表外色号处数（收口一期改小一期）
DEFERRED = {
    # 第三期：三类弹窗外壳重写时一并收口
    "gui_pyside6/dialogs/audit_dialog.py": 5,
    "gui_pyside6/dialogs/batch_operation_dialog.py": 7,
    "gui_pyside6/dialogs/filter_explainer_dialog.py": 5,
    "gui_pyside6/dialogs/ai_reason_panel.py": 1,
    "gui_pyside6/dialogs/dashboard_dialog.py": 2,
    "gui_pyside6/dialogs/flip_check_dashboard_dialog.py": 2,
    "gui_pyside6/dialogs/guizang_dialog.py": 3,
    # 第二期：看板套壳后这三个旧副本整文件删除，挂账随之消失
    "gui_pyside6/dialogs/neg_loss_dashboard_dialog.py": 1,
    "gui_pyside6/dialogs/pos_loss_dashboard_dialog.py": 1,
    "gui_pyside6/dialogs/semi_dashboard_dialog.py": 1,
    # 第五期：AuditStatusDelegate 正式接入主表时重写（当前是零引用死桩）
    "gui_pyside6/components/audit_status_delegate.py": 4,
    "gui_pyside6/widgets/audit_status_badge.py": 9,
    # 第二期：物料画像面板配色随看板抽屉一起收口
    "gui_pyside6/widgets/data_preview_panel.py": 4,
}


def _token_values(theme):
    return {v.lower() for v in TOKENS[theme].values() if isinstance(v, str)}


ALL_TOKEN_VALUES = {v.lower() for t in TOKENS.values() for v in t.values()
                    if isinstance(v, str)}


def _read(path):
    with io.open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


def _hex_in(text):
    """只取 3/6 位色号（8 位带透明度的是另一套写法，本仓 QSS 未使用）。"""
    return [h.lower() for h in HEX_RE.findall(text) if len(h) in (4, 7)]


def _docstring_nodes(tree):
    """收集所有 docstring 常量节点 id —— 它们描述的是历史色值，不参与校验。"""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                out.add(id(body[0].value))
    return out


# ------------------------------------------------------------------ 门禁 1
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_app_qss_only_uses_token_colors(theme):
    """app 级 QSS 每个色号必须是本主题令牌取值（写表外颜色即失败）。"""
    src = _read("gui_pyside6/%s_theme.qss" % theme)
    allowed = _token_values(theme)
    offenders = sorted({h for h in _hex_in(src) if h not in allowed})
    assert not offenders, "%s_theme.qss 出现表外色号 %s" % (theme, offenders)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_app_qss_has_no_legacy_primary(theme):
    src = _read("gui_pyside6/%s_theme.qss" % theme)
    offenders = sorted({h for h in _hex_in(src) if h in LEGACY_PRIMARY})
    assert not offenders, "%s_theme.qss 仍用旧主色 %s" % (theme, offenders)


# ------------------------------------------------------------------ 门禁 2
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_dashboard_qss_files_match_generator(theme):
    """themes/<theme>_dashboard.qss 是生成产物，不得手写漂移。"""
    path = "gui_pyside6/themes/%s_dashboard.qss" % theme
    assert _read(path) == build_dashboard_qss(theme), (
        "%s 与 tokens.build_dashboard_qss() 不一致，"
        "请运行 python -m gui_pyside6.themes.tokens 重新生成" % path)


# ------------------------------------------------------------------ 门禁 3
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_generated_qss_sizes_on_the_ladder(theme):
    for qss in (build_dashboard_qss(theme), build_board_qss(theme)):
        bad_r = sorted({int(x) for x in RADIUS_RE.findall(qss)} - ALLOWED_RADIUS)
        assert not bad_r, "%s 出现表外圆角 %spx（只允许 4/6/10/18）" % (theme, bad_r)
        bad_f = sorted({int(x) for x in FONT_SIZE_RE.findall(qss)} - ALLOWED_FONT_PX)
        assert not bad_f, "%s 出现表外字号 %spx（只允许 FONT_PT 档位）" % (theme, bad_f)


# ------------------------------------------------------------------ 门禁 4
def _off_token_hex_by_file():
    found = {}
    base = os.path.join(ROOT, "gui_pyside6")
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            src = io.open(full, encoding="utf-8", errors="ignore").read()
            try:
                # 被扫描文件里若有 `\Z` 这类历史遗留转义写法，Python 会发
                # DeprecationWarning —— 那是对方文件的风格问题，不该由本门禁
                # 测试向 pytest 报出来，这里就地吞掉。
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    tree = ast.parse(src, filename=full)
            except SyntaxError:
                continue
            docs = _docstring_nodes(tree)
            hits = []
            for node in ast.walk(tree):
                if (isinstance(node, ast.Constant)
                        and isinstance(node.value, str) and id(node) not in docs):
                    hits += [h for h in _hex_in(node.value)
                             if h not in ALL_TOKEN_VALUES]
            if hits:
                found[rel] = hits
    return found


def test_python_string_colors_are_tokens_or_booked():
    found = _off_token_hex_by_file()

    legacy = {f: [h for h in hs if h in LEGACY_PRIMARY] for f, hs in found.items()}
    legacy = {f: hs for f, hs in legacy.items() if hs}
    assert not legacy, "代码里仍有旧主色（5 份真源遗留）：%s" % legacy

    fresh = sorted(set(found) - set(DEFERRED))
    assert not fresh, "新增未挂账的表外色号，请改为从 tokens 取色：%s" % [
        (f, found[f]) for f in fresh]

    grew = {f: (len(found[f]), DEFERRED[f]) for f in found
            if f in DEFERRED and len(found[f]) > DEFERRED[f]}
    assert not grew, "挂账文件表外色号变多：%s" % grew


def test_deferred_bookkeeping_is_not_stale():
    """挂账只许减不许增：文件已清空/删除时必须同步删掉这一项。"""
    found = _off_token_hex_by_file()
    stale = {f: DEFERRED[f] for f in DEFERRED if len(found.get(f, [])) < DEFERRED[f]}
    assert not stale, (
        "这些挂账已经变少或消失，请把 DEFERRED 里的数字改小或删除该项：%s" % stale)


# ------------------------------------------------------------------ 令牌表自检
def test_token_tables_have_same_keys():
    """两套主题的令牌键必须一一对应，否则 Thm.color 在暗色下会 KeyError。"""
    assert set(TOKENS["light"]) == set(TOKENS["dark"])


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_token_values_are_valid_hex(theme):
    for key, val in TOKENS[theme].items():
        if isinstance(val, str) and val.startswith("#"):
            assert re.fullmatch(r"#[0-9A-Fa-f]{6}", val), (theme, key, val)
