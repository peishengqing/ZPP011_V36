#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZPP011 高级报告生成器 v2 (基于企业级模板)
生成20+页专业PPT，包含封面、目录、KPI卡片、图表、表格等
"""
import os
import datetime
from io import BytesIO
from typing import Dict, List, Tuple

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.chart import XL_CHART_TYPE
from pptx.chart.data import ChartData

# ========== 日志兜底（v43.156）============
def _safe_log(log_cb, msg, level="info"):
    """调用外部 log_cb，且绝不因日志本身的问题让生成流程崩掉。

    v43.156 修复的致命 bug：旧代码写的是 `log_cb(f"生成失败：{e}")`（只传 1 个参数），
    而 GUI 侧传入的 `MainWindow.log` 签名是 `(msg, level)`。一旦生成失败，
    这行本身抛 `TypeError: missing 1 required positional argument`，
    **把原始异常顶掉**——用户看到的报错与真实原因毫无关系，现场零线索。

    这里做三层兜底：
      1. 优先按 (msg, level) 调用（正规签名）
      2. 传参失败 → 降级为单参 log_cb(msg)
      3. 仍失败 → 静默吞掉（日志绝不反噬主流程）
    """
    if not log_cb:
        return
    try:
        log_cb(msg, level)
        return
    except TypeError:
        pass
    except Exception:
        return
    try:
        log_cb(msg)
    except Exception:
        pass


# ========== 目录页搬运（v43.156）============
def _move_slide_to(prs, old_index, new_index):
    """把 prs.slides[old_index] 移动到 prs.slides[new_index]（python-pptx 不支持插页，只能搬）。

    原理：sldIdLst 里每个 <p:sldId> 的 r:id 指向一个 slide part，
    只要重排 <p:sldId> 元素的顺序即可改变呈现顺序，slide part 本身不动
    （母版/版式/图片关系全部保持原样，最安全）。

    old_index / new_index 均为 0-based。
    """
    xml_slides = prs.slides._sldIdLst
    slides = list(xml_slides)
    if not (0 <= old_index < len(slides)) or not (0 <= new_index < len(slides)):
        return False
    if old_index == new_index:
        return True
    el = slides[old_index]
    xml_slides.remove(el)
    # remove 后重新取列表，插入到目标位置
    xml_slides.insert(new_index, el)
    return True


def _drop_blank_slides(generator, min_shapes=1):
    """删除「一个 shape 都没有」的空白页，返回删除数量。

    v43.156：目录搬运改用「不预留占位」方案后已不会产生空白页，
    但保留这层兜底——将来若再引入占位/预留逻辑，多余的空白页会被自动清掉，
    不会静默留在交付给用户的报告里（用户看到全白页会以为文件坏了）。
    """
    prs = generator.prs
    xml_slides = prs.slides._sldIdLst
    removed = 0
    # 从后往前删，避免索引位移
    for idx in range(len(xml_slides) - 1, -1, -1):
        sldId = xml_slides[idx]
        try:
            part = prs.part.related_part(sldId.rId)
        except Exception:
            continue
        try:
            n = len(part.shapes)
        except Exception:
            continue
        if n < min_shapes:
            rid = sldId.rId
            xml_slides.remove(sldId)
            try:
                prs.part.drop_rel(rid)
            except Exception:
                pass
            removed += 1
    return removed


# ========== 配置区域 ==========
COMPANY_NAME = "云南达利生产基地"
REPORT_TITLE = "ZPP011 生产偏差分析报告"
AUTHOR = "ZPP011 系统"
TEMPLATE_PATH = None  # 使用内置模板
OUTPUT_DIR = "ZPP011分析报告"  # 相对路径
CHINESE_FONT = "Microsoft YaHei"
PRIMARY_COLOR = RGBColor(30, 60, 114)  # 深蓝色（主色）
SECONDARY_COLOR = RGBColor(0, 112, 192)  # 亮蓝色（辅色）
ACCENT_COLOR = RGBColor(255, 152, 0)  # 橙色（强调）
POSITIVE_COLOR = RGBColor(220, 53, 69)  # 红色（正偏差）
NEGATIVE_COLOR = RGBColor(40, 167, 69)  # 绿色（负偏差）

# ========== 辅助函数 ==========
def _format_text_frame(element, font_size=18, bold=False, italic=False,
                      color=RGBColor(0, 0, 0), alignment=PP_ALIGN.LEFT,
                      space_after=Pt(6)):
    """统一文本格式化"""
    if hasattr(element, 'text_frame'):
        tf = element.text_frame
    else:
        tf = element
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    for paragraph in tf.paragraphs:
        paragraph.alignment = alignment
        paragraph.space_after = space_after
        for run in paragraph.runs:
            run.font.name = CHINESE_FONT
            run.font.size = Pt(font_size)
            run.font.bold = bold
            run.font.italic = italic
            run.font.color.rgb = color

def _add_table(slide, left, top, width, headers, rows, col_widths=None):
    """通用表格添加函数 (修复列宽类型错误)"""
    n_rows = len(rows) + 1
    n_cols = len(headers)
    
    # ⚠️ 关键修复：所有数值必须是纯 int (EMU单位)
    # 不管输入是什么类型，强制转为纯 int
    
    # 行高：0.45英寸 → EMU整数（纯 int）
    row_h = int(0.45 * 914400)  # 411480 EMU (纯 int)
    tbl_h = int(row_h * n_rows)  # 强制转纯 int
    
    # left, top, width 强制转纯 int
    # 使用 try-except 处理各种可能的类型
    try:
        left = int(left)
    except (TypeError, ValueError):
        left = int(left.emus) if hasattr(left, 'emus') else left
    
    try:
        top = int(top)
    except (TypeError, ValueError):
        top = int(top.emus) if hasattr(top, 'emus') else top
    
    try:
        width = int(width)
    except (TypeError, ValueError):
        width = int(width.emus) if hasattr(width, 'emus') else width
    
    # 现在所有参数都是纯 int，调用 add_table
    table = slide.shapes.add_table(n_rows, n_cols, left, top, width, tbl_h).table

    # ========== 列宽处理（转为纯 int EMU）==========
    # v43.156：先裁剪到实际列数。旧版直接 enumerate(col_widths) 越界访问
    # table.columns[i] 抛 "column index out of range"，而 except 分支里的
    # 兜底赋值 table.columns[i] 又用同一个越界 i → 二次崩溃，整份报告生成失败。
    # 典型触发：表头是动态拼的（如「偏差最大明细」按存在列取），列数会变，
    # 而调用方给了固定长度的 col_widths。
    if col_widths:
        if len(col_widths) > n_cols:
            col_widths = list(col_widths)[:n_cols]
        elif len(col_widths) < n_cols:
            col_widths = list(col_widths) + [1.5] * (n_cols - len(col_widths))
        for i, w in enumerate(col_widths):
            try:
                # 将英寸值转为纯 int (EMU)
                # 关键：先转 float，乘以 914400，再转纯 int
                if isinstance(w, str):
                    w = float(w)

                # 计算 EMU 值，并强制转纯 int
                emu_val = int(w * 914400)  # w 现在是 int 或 float

                # ⚠️ 关键修复：确保赋值时是纯 int
                table.columns[i].width = int(emu_val)  # 强制转纯 int

            except Exception as e:
                print(f"[ERROR] 列宽转换失败: {w}, 错误: {e}")
                # 使用默认宽度（纯 int）；此处 i 已保证 < n_cols，不会二次越界
                table.columns[i].width = int(1.5 * 914400)  # 1371600 EMU
    # ============================================

    # 表头
    for i, h in enumerate(headers):
        cell = table.cell(0, i)
        cell.text = str(h)
        cell.fill.solid()
        cell.fill.fore_color.rgb = PRIMARY_COLOR
        for p in cell.text_frame.paragraphs:
            p.font.size = Pt(12)
            p.font.bold = True
            p.font.color.rgb = RGBColor(255, 255, 255)
            p.alignment = PP_ALIGN.CENTER

    # 数据行
    for r_idx, row in enumerate(rows, 1):
        for c_idx, val in enumerate(row):
            cell = table.cell(r_idx, c_idx)
            cell.text = str(val)
            if r_idx % 2 == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor(245, 245, 245)
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(11)
                p.font.color.rgb = RGBColor(50, 50, 50)
                p.alignment = PP_ALIGN.CENTER
            if c_idx in [2, 3, 4] and isinstance(val, (int, float)) and val < 0:
                for p in cell.text_frame.paragraphs:
                    p.font.color.rgb = NEGATIVE_COLOR

def _create_bar_chart_image(df, x_col, y_col, title, xlabel, ylabel, color=PRIMARY_COLOR):
    """使用 matplotlib 生成柱状图并返回图片流"""
    if df.empty:
        return None
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(df[x_col], df[y_col], color=color)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    img_buf = BytesIO()
    plt.savefig(img_buf, format='png', dpi=100, bbox_inches='tight')
    plt.close()
    img_buf.seek(0)
    return img_buf

# ========== 核心生成器 ==========
class AdvancedPPTGeneratorV2:
    def __init__(self):
        self.prs = Presentation(TEMPLATE_PATH) if TEMPLATE_PATH else self._create_base_template()
        self.slide_width = self.prs.slide_width
        self.slide_height = self.prs.slide_height
        self.toc_entries = []  # [(title, slide_index), ...]
        self.current_section = ""

    def _create_base_template(self):
        """创建基础模板（含空白版式和内容版式）"""
        prs = Presentation()
        # 清空所有默认版式（可选，为了简化我们使用默认布局）
        # 直接使用默认版式即可，通过添加空白页和标题页来实现
        return prs

    def add_title_slide(self):
        """添加封面页"""
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])  # 空白
        # 背景色
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, self.slide_width, self.slide_height)
        bg.fill.solid()
        bg.fill.fore_color.rgb = PRIMARY_COLOR
        bg.line.fill.background()
        # 标题
        tx = slide.shapes.add_textbox(Inches(1), Inches(2), self.slide_width - Inches(2), Inches(1.5))
        tf = tx.text_frame
        p = tf.paragraphs[0]
        p.text = REPORT_TITLE
        p.font.size = Pt(44)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)
        p.alignment = PP_ALIGN.CENTER
        # 副标题
        tx2 = slide.shapes.add_textbox(Inches(1), Inches(3.5), self.slide_width - Inches(2), Inches(0.8))
        tf2 = tx2.text_frame
        p2 = tf2.paragraphs[0]
        p2.text = f"{COMPANY_NAME} | {datetime.datetime.now().strftime('%Y-%m-%d')}"
        p2.font.size = Pt(18)
        p2.font.color.rgb = RGBColor(200, 200, 200)
        p2.alignment = PP_ALIGN.CENTER
        # 版本信息
        tx3 = slide.shapes.add_textbox(Inches(1), Inches(5.5), self.slide_width - Inches(2), Inches(0.5))
        tf3 = tx3.text_frame
        p3 = tf3.paragraphs[0]
        p3.text = f"数据周期：基于最新分析 | 生成：{AUTHOR}"
        p3.font.size = Pt(12)
        p3.font.color.rgb = RGBColor(160, 160, 160)
        p3.alignment = PP_ALIGN.CENTER

    def add_toc_slide(self):
        """添加目录页（基于已记录的章节）"""
        if not self.toc_entries:
            return
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        self._add_section_header(slide, "目录")
        left = Inches(1.5)
        top = Inches(1.8)
        width = self.slide_width - Inches(3)
        height = Inches(0.6 * len(self.toc_entries))
        tx = slide.shapes.add_textbox(left, top, width, height)
        tf = tx.text_frame
        tf.word_wrap = True
        for i, (title, idx) in enumerate(self.toc_entries, 1):
            p = tf.add_paragraph()
            p.text = f"{i}. {title}"
            p.font.size = Pt(24)
            p.font.color.rgb = PRIMARY_COLOR
            p.space_after = Pt(12)
            # 可添加超链接，但需保存后生效
            # p.hyperlink.address = f"#slide={idx+1}"

    def add_section(self, title: str):
        """开始新章节（自动记录到目录）"""
        self.current_section = title
        self.toc_entries.append((title, len(self.prs.slides)))

    def add_kpi_slide(self, kpis: List[Tuple[str, str, RGBColor]]):
        """添加KPI卡片页（每行最多4个）"""
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        self._add_section_header(slide, "核心指标概览")
        cols = 4
        card_width = Inches(2.8)
        card_height = Inches(1.5)
        start_x = (self.slide_width - (cols * card_width + (cols - 1) * Inches(0.2))) / 2
        for i, (label, value, color) in enumerate(kpis):
            row = i // cols
            col = i % cols
            left = start_x + col * (card_width + Inches(0.2))
            top = Inches(1.8) + row * (card_height + Inches(0.2))
            # 卡片背景
            card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, card_width, card_height)
            card.fill.solid()
            card.fill.fore_color.rgb = RGBColor(255, 255, 255)
            card.line.color.rgb = RGBColor(210, 210, 210)
            card.line.width = 12700  # 1磅 = 12700 EMU
            # 左侧色条
            stripe = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, Inches(0.1), card_height)
            stripe.fill.solid()
            stripe.fill.fore_color.rgb = color
            stripe.line.fill.background()
            # 数值
            tx_val = slide.shapes.add_textbox(left + Inches(0.2), top + Inches(0.2), card_width - Inches(0.3), Inches(0.8))
            tf_val = tx_val.text_frame
            p_val = tf_val.paragraphs[0]
            p_val.text = str(value)
            p_val.font.size = Pt(28)
            p_val.font.bold = True
            p_val.font.color.rgb = color
            # 标签
            tx_lbl = slide.shapes.add_textbox(left + Inches(0.2), top + Inches(0.9), card_width - Inches(0.3), Inches(0.4))
            tf_lbl = tx_lbl.text_frame
            p_lbl = tf_lbl.paragraphs[0]
            p_lbl.text = label
            p_lbl.font.size = Pt(12)
            p_lbl.font.color.rgb = RGBColor(80, 80, 80)

    def add_chart_slide(self, title: str, chart_data: Dict):
        """添加图表页"""
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        self._add_section_header(slide, title)
        # 所有数值强制转 int (EMU)
        chart_left = int(Inches(0.8))
        chart_top = int(Inches(1.6))
        chart_width = int(int(self.slide_width) - int(Inches(1.6)))
        chart_height = int(Inches(4.8))
        self._add_chart(slide, chart_data, chart_left, chart_top, chart_width, chart_height)

    def add_table_slide(self, title: str, headers: List[str], rows: List[List], col_widths: List[float] = None):
        """添加表格页"""
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        self._add_section_header(slide, title)
        # 所有数值转为 int (EMU) 类型
        left = int(Inches(0.8))       # 0.8英寸 → EMU整数
        top = int(Inches(1.6))        # 1.6英寸 → EMU整数
        width = int(self.slide_width) - int(Inches(1.6))  # 强行转int再减
        _add_table(slide, left, top, width, headers, rows, col_widths)

    def add_text_slide(self, title: str, content: List[str]):
        """添加纯文本页（项目符号列表）"""
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        self._add_section_header(slide, title)
        tx = slide.shapes.add_textbox(Inches(0.8), Inches(1.8), self.slide_width - Inches(1.6), Inches(5))
        tf = tx.text_frame
        tf.word_wrap = True
        for line in content:
            p = tf.add_paragraph()
            p.text = line
            p.font.size = Pt(20)
            p.font.color.rgb = RGBColor(50, 50, 50)
            p.space_after = Pt(12)

    def _add_section_header(self, slide, title: str):
        """添加章节标题栏"""
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, self.slide_width, Inches(1.1))
        bar.fill.solid()
        bar.fill.fore_color.rgb = PRIMARY_COLOR
        bar.line.fill.background()
        tx = slide.shapes.add_textbox(Inches(0.5), Inches(0.2), self.slide_width - Inches(1), Inches(0.7))
        tf = tx.text_frame
        p = tf.paragraphs[0]
        p.text = title
        p.font.size = Pt(28)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)

    def _add_chart(self, slide, data: Dict, left, top, width, height):
        """添加PPT内置图表（柱状图/折线图/饼图）"""
        chart_type_str = data.get("type", "bar")
        categories = data["categories"]
        series_list = data["series"]  # list of dict with 'name' and 'values'
        chart_data = ChartData()
        chart_data.categories = categories
        for s in series_list:
            chart_data.add_series(s["name"], s["values"])
        if chart_type_str == "bar":
            chart_type = XL_CHART_TYPE.COLUMN_CLUSTERED
        elif chart_type_str == "line":
            chart_type = XL_CHART_TYPE.LINE
        elif chart_type_str == "pie":
            chart_type = XL_CHART_TYPE.PIE
        else:
            chart_type = XL_CHART_TYPE.COLUMN_CLUSTERED
        chart = slide.shapes.add_chart(chart_type, left, top, width, height, chart_data).chart
        if chart_type_str != "pie":
            chart.has_legend = True
            chart.legend.include_in_layout = False
            # 设置系列颜色
            for i, ser in enumerate(chart.series):
                ser.format.fill.solid()
                ser.format.fill.fore_color.rgb = PRIMARY_COLOR if i == 0 else SECONDARY_COLOR
                ser.data_labels.font.size = Pt(10)
        else:
            chart.has_legend = True

    def save(self, output_path: str):
        """保存文件"""
        self.prs.save(output_path)
        return output_path

# ========== 数据适配函数 ==========
def _load_data_from_excel(excel_path):
    """从Excel读取必要的数据集

    v43.156：缺 sheet 时不再只抛「缺少必要的 Sheet」这种看不懂的错，
    而是区分「原始导入表」与「分析结果导出文件」两种情形给出可执行提示。
    """
    from utils.excel_io import open_excel_book
    if not excel_path or not os.path.exists(excel_path):
        raise FileNotFoundError("找不到 Excel 文件：%s" % (excel_path or "(空路径)"))
    xl = open_excel_book(excel_path)
    sheets = xl.sheet_names
    data = {}
    if '汇总统计' in sheets:
        data['summary'] = xl.parse('汇总统计')
    if '完整偏差明细' in sheets:
        data['detail'] = xl.parse('完整偏差明细')
    if '替代料明细' in sheets:
        data['alt'] = xl.parse('替代料明细')
    if '偏差原因分析' in sheets:
        data['cause'] = xl.parse('偏差原因分析')

    # v43.156：把「为什么不行」讲清楚。最常见的是用户直接把原始导入表
    # （只有 Data 一个 sheet）喂进来——旧代码只说「缺少必要的 Sheet」，
    # 用户根本想不到是自己导错了文件。
    if data.get('summary') is None or data.get('detail') is None:
        missing = []
        if data.get('summary') is None:
            missing.append('汇总统计')
        if data.get('detail') is None:
            missing.append('完整偏差明细')
        if len(sheets) == 1 and sheets[0] == 'Data':
            raise ValueError(
                "这是**原始导入表**（只有 Data 一个工作表），不是分析结果。\n"
                "智能PPT 需要分析结果：请先在主界面点「分析」，"
                "再用「导出完整报告」得到含 %s 的 Excel，再点智能PPT。\n"
                "（当前文件的工作表：%s）" % (' / '.join(missing), ', '.join(sheets))
            )
        raise ValueError(
            "Excel 缺少必要的工作表：%s。\n"
            "请确认选的是「分析后导出的完整报告」，而不是原始导入表。\n"
            "（当前文件的工作表：%s）" % (' / '.join(missing), ', '.join(sheets) if sheets else "(空)")
        )
    return data

def generate_advanced_report_v2(excel_path, output_path, log_cb=None, mode="pro"):
    """生成高级报告 v2（供 GUI 调用）

    mode（v43.156 新增，修复「简明版与专业版是同一份报告」）：
      "simple" —— 简明版：封面/目录/KPI/核心结论，约 4-5 页，给管理层看结论
      "pro"    —— 专业版：封面/目录/多章节 + 深度表图，20+ 页，给执行层看细节

    旧版两个入口都走默认路径且共用同一套 add_* 调用，产出字节数完全一致，
    菜单里「专业版(20+页)」纯属摆设。现按 mode 分流。
    """
    try:
        if mode not in ("simple", "pro"):
            raise ValueError("mode 只能是 'simple' 或 'pro'，收到：%r" % (mode,))
        is_pro = (mode == "pro")
        data = _load_data_from_excel(excel_path)
        summary = data.get('summary')
        detail = data.get('detail')
        alt = data.get('alt')
        cause = data.get('cause')

        pt = AdvancedPPTGeneratorV2()
        # 1. 封面
        pt.add_title_slide()
        # 2. 目录：v43.156 改为「内容加完后再生成，然后搬到第 2 页」。
        #    旧版在所有内容加完才 add_toc_slide()，导致目录落在最后一页
        #    （源码注释自认「本版就放在末尾」），用户得翻到第 10 页才看到目录。
        _safe_log(log_cb, "开始生成%s报告…" % ("专业版" if is_pro else "简明版"))

        # 3. 计算核心KPI（添加列名映射，增强兼容性）
        summary_cols = summary.columns.tolist()

        # 总条数
        total_rows_col = next((c for c in ['总条数', '记录数', '条数'] if c in summary_cols), None)
        total_rows = int(summary[total_rows_col].sum()) if total_rows_col else len(summary)

        # 正偏差条数
        pos_cnt_col = next((c for c in ['正偏差条数', '正偏差记录数'] if c in summary_cols), None)
        pos_cnt = int(summary[pos_cnt_col].sum()) if pos_cnt_col else 0

        # 负偏差条数
        neg_cnt_col = next((c for c in ['负偏差条数', '负偏差记录数'] if c in summary_cols), None)
        neg_cnt = int(summary[neg_cnt_col].sum()) if neg_cnt_col else 0

        # 正偏差金额(含税)
        pos_amt_col = next((c for c in ['正偏差金额(含税)', '正偏差金额'] if c in summary_cols), None)
        pos_amount = summary[pos_amt_col].sum() if pos_amt_col else 0

        # 负偏差金额(含税)
        neg_amt_col = next((c for c in ['负偏差金额(含税)', '负偏差金额'] if c in summary_cols), None)
        neg_amount = abs(summary[neg_amt_col].sum()) if neg_amt_col else 0
        net_amount = pos_amount - neg_amount
        # 备注覆盖率（加权）
        rate_col_name = next((c for c in ['备注覆盖率', '备注覆盖', '覆盖率'] if c in summary.columns), None)
        if rate_col_name:
            rate_col = summary[rate_col_name]
            rates = rate_col.astype(str).str.replace('%', '').astype(float) / 100
            weight_col = next((c for c in ['总条数', '记录数', '条数'] if c in summary.columns), None)
            weights = summary[weight_col] if weight_col else pd.Series([1] * len(summary))
        else:
            rates = pd.Series([0.0] * max(len(summary), 1))
            weights = pd.Series([1] * max(len(summary), 1))
        note_rate = (rates * weights).sum() / weights.sum() if weights.sum() > 0 else 0
        kpis = [
            ("总记录数", f"{total_rows:,}", PRIMARY_COLOR),
            ("正偏差（多耗）", f"{pos_cnt:,}", POSITIVE_COLOR),
            ("负偏差（少耗）", f"{neg_cnt:,}", NEGATIVE_COLOR),
            ("净偏差(元)", f"{net_amount:,.0f}", ACCENT_COLOR),
            ("备注覆盖率", f"{note_rate:.1%}", SECONDARY_COLOR),
        ]
        pt.add_kpi_slide(kpis)

        # ---- 以下为「仅专业版」内容（v43.156）----
        if is_pro:
            pt.add_section("一、总体与维度对比")
            _safe_log(log_cb, "生成章节：总体与维度对比")

            # 4. 工厂对比（如果有工厂列）
            factory_col = next((c for c in ['工厂', '工厂名称'] if c in summary.columns), None)
            if factory_col:
                # v43.156：旧版硬编码列名 '总条数'/'正偏差金额(含税)'/'负偏差金额(含税)'，
                # 一旦 summary 列名变（如「负偏差金额」）就 KeyError 整份报告生成失败。
                # 现统一走列名映射，与上面 KPI 部分口径一致。
                f_cnt_col = total_rows_col or '总条数'
                f_pos_col = pos_amt_col or '正偏差金额(含税)'
                f_neg_col = neg_amt_col or '负偏差金额(含税)'
                factory_data = summary.groupby(factory_col).agg({
                    f_cnt_col: 'sum', f_pos_col: 'sum',
                    f_neg_col: lambda x: abs(x.sum())
                }).reset_index()
                factory_data.columns = [factory_col, '记录数', '正偏差金额', '负偏差金额']
                factory_data['净偏差'] = factory_data['正偏差金额'] - factory_data['负偏差金额']
                headers = ['工厂', '记录数', '正偏差(万元)', '负偏差(万元)', '净偏差(万元)']
                rows = []
                for _, r in factory_data.iterrows():
                    rows.append([
                        r[factory_col], int(r['记录数']),
                        f"{r['正偏差金额']/10000:.1f}",
                        f"{r['负偏差金额']/10000:.1f}",
                        f"{r['净偏差']/10000:.1f}"
                    ])
                pt.add_table_slide("工厂维度对比", headers, rows, col_widths=[2, 1, 1.5, 1.5, 1.5])
            else:
                # v43.156：无工厂维度时给说明页，而非整页消失
                pt.add_text_slide("工厂维度对比（本期无数据）", [
                    "• 汇总统计中未找到「工厂」或「工厂名称」列，无法做工厂对比",
                    "• 工厂维度用于定位是哪家工厂/车间贡献了偏差",
                    "• 请确认导出时「汇总统计」包含工厂字段",
                ])

            # 5. 车间偏差排行（Top10）
            detail_amt_col = next((c for c in ['偏差金额', '偏差金额(含税)'] if c in detail.columns), None)
            workshop_col = next((c for c in ['车间', '生产管理员描述'] if c in detail.columns), None)
            if workshop_col and detail_amt_col:
                workshop_rank = detail.groupby(workshop_col)[detail_amt_col].apply(
                    lambda x: x.abs().sum()).nlargest(10).reset_index()
                workshop_rank.columns = ['车间', '偏差金额(元)']
                pt.add_table_slide("车间偏差金额排行(Top10)", ['车间', '偏差金额(元)'],
                                  [[r['车间'], f"{r['偏差金额(元)']:,.0f}"] for _, r in workshop_rank.iterrows()],
                                  col_widths=[4, 4])

            # 6. 物料偏差排行（Top10）
            mat_col = next((c for c in ['物料编码', '组件物料号'] if c in detail.columns), None)
            if mat_col and detail_amt_col:
                mat_rank = detail.groupby(mat_col)[detail_amt_col].apply(
                    lambda x: x.abs().sum()).nlargest(10).reset_index()
                mat_rank.columns = ['物料编码', '偏差金额(元)']
                name_col = next((c for c in ['物料名称', '组件物料描述'] if c in detail.columns), None)
                if name_col:
                    name_map = detail[[mat_col, name_col]].drop_duplicates()
                    mat_rank = mat_rank.merge(name_map, on=mat_col, how='left')
                    headers = ['物料编码', '物料名称', '偏差金额(元)']
                    rows = [[r['物料编码'], r[name_col], f"{r['偏差金额(元)']:,.0f}"]
                            for _, r in mat_rank.iterrows()]
                    pt.add_table_slide("物料偏差金额排行(Top10)", headers, rows, col_widths=[2, 5, 2])
                else:
                    pt.add_table_slide("物料偏差金额排行(Top10)", ['物料编码', '偏差金额(元)'],
                                      [[r['物料编码'], f"{r['偏差金额(元)']:,.0f}"] for _, r in mat_rank.iterrows()],
                                      col_widths=[3, 5])

            # 6b. 物料类型维度（v43.156 新增，专业版专属）
            # v43.156：列名兜底加「物料类型」——实测明细表里有时没有
            # 「组件物料类型描述」只有「物料类型」，旧候选表会整页消失。
            type_col = next((c for c in ['组件物料类型描述', '组件物料类型', '物料类型']
                             if c in detail.columns), None)
            if type_col and detail_amt_col:
                type_rank = detail.groupby(type_col)[detail_amt_col].apply(
                    lambda x: x.abs().sum()).nlargest(12).reset_index()
                type_rank.columns = ['物料类型', '偏差金额(元)']
                pt.add_table_slide("物料类型偏差金额排行(Top12)", ['物料类型', '偏差金额(元)'],
                                  [[str(r['物料类型'])[:20], f"{r['偏差金额(元)']:,.0f}"]
                                   for _, r in type_rank.iterrows()],
                                  col_widths=[4, 4])
            else:
                pt.add_text_slide("物料类型维度（本期无数据）", [
                    "• 明细中未找到物料类型列（组件物料类型描述/组件物料类型/物料类型）",
                    "• 物料类型维度是识别「包材 vs 原料」偏差结构的关键视角",
                    "• 请确认导出时「完整偏差明细」包含物料类型字段",
                ])

            # 6c. TOP 物料图表（v43.156 新增）
            if mat_col and detail_amt_col:
                top8 = detail.groupby(mat_col)[detail_amt_col].apply(
                    lambda x: x.abs().sum()).nlargest(8)
                if not top8.empty:
                    pt.add_chart_slide("偏差金额 TOP8 物料", {
                        "type": "bar",
                        "categories": [str(i) for i in top8.index],
                        "series": [{"name": "偏差金额(元)", "values": [float(v) for v in top8.values]}],
                    })

            pt.add_section("二、结构性诊断")

            # 6d-0. 偏差集中度（v43.156 新增）
            # 只依赖 detail + 偏差金额列，是本节「必出页」——保证不同数据下
            # 专业版页数稳定，不会因某个维度列缺失就整页消失。
            if detail_amt_col:
                amt_abs = detail[detail_amt_col].abs().sort_values(ascending=False)
                tot = amt_abs.sum()
                if tot > 0:
                    top10_share = amt_abs.head(10).sum() / tot
                    top50_share = amt_abs.head(50).sum() / tot
                    top100_share = amt_abs.head(100).sum() / tot
                    pt.add_text_slide("偏差集中度（钱集中在少数物料上）", [
                        f"• 偏差金额合计（绝对值）：{tot:,.0f} 元",
                        f"• TOP10 物料占：{top10_share:.1%}",
                        f"• TOP50 物料占：{top50_share:.1%}",
                        f"• TOP100 物料占：{top100_share:.1%}",
                        "",
                        ("• 集中度很高：少数物料就吃掉了大部分偏差金额，"
                         "抓这些物料的定额与领用即可见效"
                         if top10_share > 0.5 else
                         "• 集中度一般：偏差分散在较多物料上，"
                         "宜从流程/系统层面治理，而非逐个物料盯"),
                        "• 治本优先级：TOP10 物料 → 补备注 → 核定额 → 查领用",
                    ])

            # 6d. 偏差率分布（v43.156 新增）
            rate_col = next((c for c in ['偏差率(%)', '偏差率'] if c in detail.columns), None)
            rate_ok = False
            if rate_col:
                try:
                    buckets = pd.cut(
                        pd.to_numeric(detail[rate_col], errors='coerce'),
                        bins=[-float('inf'), -50, -20, 0, 20, 50, float('inf')],
                        labels=['<-50%', '-50~-20%', '-20~0%', '0~20%', '20~50%', '>50%'])
                    dist = buckets.value_counts().reindex(
                        ['<-50%', '-50~-20%', '-20~0%', '0~20%', '20~50%', '>50%']).fillna(0)
                    pt.add_chart_slide("偏差率分布（按记录数）", {
                        "type": "bar",
                        "categories": [str(i) for i in dist.index],
                        "series": [{"name": "记录数", "values": [int(v) for v in dist.values]}],
                    })
                    rate_ok = True
                except Exception:
                    # v43.156：旧版这里裸 pass，偏差率列一旦是脏数据（文本/空串）
                    # 整页静默消失，用户以为报告缺内容。改为吞掉后走兜底说明页。
                    rate_ok = False
            if not rate_ok:
                pt.add_text_slide("偏差率分布（本期无法统计）", [
                    "• 明细中未找到可用的「偏差率」列，或该列含无法解析的脏数据",
                    "• 偏差率分布能看出「整体偏差是个别物料的极端值，还是普遍性偏移」",
                    "• 个别极端值 → 查该物料定额/领用；普遍偏移 → 查系统与流程",
                    "• 请确认导出时「完整偏差明细」包含数值型偏差率字段",
                ])

            # 6e. 车间对比图表（v43.156 新增）
            if workshop_col and detail_amt_col:
                ws = detail.groupby(workshop_col)[detail_amt_col].apply(
                    lambda x: x.abs().sum()).nlargest(8)
                if not ws.empty:
                    pt.add_chart_slide("车间偏差金额 TOP8", {
                        "type": "bar",
                        "categories": [str(i) for i in ws.index],
                        "series": [{"name": "偏差金额(元)", "values": [float(v) for v in ws.values]}],
                    })

            # 6f. 偏差方向结构（v43.156 新增，必出页）
            # 只依赖 偏差金额 一列，任何数据下都能算——多耗/少耗的钱各占多少，
            # 是管理层最想先知道的结构性问题。
            if detail_amt_col:
                v = pd.to_numeric(detail[detail_amt_col], errors='coerce').dropna()
                pos = v[v > 0].sum()
                neg = v[v < 0].abs().sum()
                tot2 = pos + neg
                if tot2 > 0:
                    pt.add_text_slide("偏差方向结构（多耗 vs 少耗）", [
                        f"• 多耗（正偏差）金额：{pos:,.0f} 元（{pos/tot2:.1%}）",
                        f"• 少耗（负偏差）金额：{neg:,.0f} 元（{neg/tot2:.1%}）",
                        f"• 净额：{pos - neg:,.0f} 元",
                        "",
                        ("• 多耗远大于少耗 → 领用/投料环节存在系统性超领，"
                         "重点查定额与领用环节" if pos > neg * 2 else
                         "• 少耗远大于多耗 → 存在大量负偏差，可能是替代料镜像抵消"
                         "或领用未登记，建议先排查替代料配对" if neg > pos * 2 else
                         "• 多耗与少耗大致相当 → 多为规格切换/镜像抵消，"
                         "需用替代料净偏差口径看真实成本"),
                        "• 注意：账面偏差合计 ≠ 真实成本，替代料必须做净额抵消",
                    ])

            # 7. 替代料机制（如果有数据）
            pt.add_section("三、替代料与根因")
            if alt is not None and hasattr(alt, 'empty') and not alt.empty:
                alt_sample = alt.head(3)
                headers = ['物料A', '偏差A', '物料B', '偏差B', '净偏差']
                rows = []
                for _, r in alt_sample.iterrows():
                    rows.append([
                        str(r.get('物料A', ''))[:20], f"{r.get('偏差金额A', 0):,.0f}",
                        str(r.get('物料B', ''))[:20], f"{r.get('偏差金额B', 0):,.0f}",
                        f"{r.get('净偏差', 0):,.0f}"
                    ])
                pt.add_table_slide("替代料核对机制（示例）", headers, rows,
                                   col_widths=[2.5, 1.5, 2.5, 1.5, 1.5])
                pt.add_text_slide("替代料机制价值", [
                    "• 镜像偏差：原物料-100%，替代料+100%",
                    "• 净偏差 = 物料A + 物料B，反映真实成本",
                    "• 金黄胚系列净偏差-6万 vs 账面143万",
                    "• 避免将规格切换误判为管理异常"
                ])
                # v43.156：替代料全量 TOP（专业版专属）
                alt_net_col = next((c for c in ['净偏差', '净偏差金额'] if c in alt.columns), None)
                if alt_net_col:
                    alt_rank = alt.groupby('物料A')[alt_net_col].apply(
                        lambda x: x.abs().sum()).nlargest(10).reset_index() \
                        if '物料A' in alt.columns else None
                    if alt_rank is not None and not alt_rank.empty:
                        alt_rank.columns = ['物料A', '净偏差绝对值(元)']
                        pt.add_table_slide("替代料净偏差 TOP10（物料A）",
                                          ['物料A', '净偏差绝对值(元)'],
                                          [[str(r['物料A'])[:22], f"{r['净偏差绝对值(元)']:,.0f}"]
                                           for _, r in alt_rank.iterrows()],
                                          col_widths=[4, 4])
            else:
                # v43.156：本节无数据时给出说明页，而不是静默跳过。
                # 静默跳过会让「专业版(20+页)」在不同数据下页数飘忽（实测
                # 替代料明细为空表时整体只有 17 页），用户以为报告缺内容。
                pt.add_text_slide("替代料核对机制（本期无数据）", [
                    "• 本期分析结果中「替代料明细」为空，未发现替代料配对",
                    "• 若确实存在替代料，请确认导出时勾选了「替代料明细」",
                    "• 无替代料时，账面偏差即为真实偏差，无需做镜像抵消",
                    "• 替代料机制仅在发生规格切换时生效，"
                    "镜像偏差（原物料-100% / 替代料+100%）互相抵消",
                ])

            # 8. 根因诊断（如果有原因分析）
            if cause is not None and hasattr(cause, 'empty') and not cause.empty \
                    and '备注原因' in cause.columns:
                cause_counts = cause['备注原因'].value_counts().head(10).reset_index()
                cause_counts.columns = ['原因', '频次']
                pt.add_table_slide("主要偏差原因 Top10", ['原因', '频次'],
                                  [[str(r['原因'])[:26], int(r['频次'])]
                                   for _, r in cause_counts.iterrows()],
                                  col_widths=[6, 2])
                pt.add_chart_slide("偏差原因分布（Top10）", {
                    "type": "bar",
                    "categories": [str(r['原因'])[:18] for _, r in cause_counts.iterrows()],
                    "series": [{"name": "频次", "values": [int(r['频次']) for _, r in cause_counts.iterrows()]}],
                })
            else:
                # v43.156：同替代料，无数据也给说明页，保证专业版页数稳定
                pt.add_text_slide("根因诊断（本期无归因数据）", [
                    "• 本期「偏差原因分析」为空或缺少「备注原因」列",
                    "• 根因分析依赖人工填写备注，备注为空则无法归因",
                    "• 请确认导出时包含「偏差原因分析」工作表",
                    "• 建议：把「强制补录备注」作为立即行动的第一项",
                ])

            # 8b. 无备注预警（v43.156 新增）
            note_col = next((c for c in ['备注', '备注原因'] if c in detail.columns), None)
            blank_amt = None
            if note_col and detail_amt_col:
                blank_note = detail[detail[note_col].fillna('').astype(str).str.strip() == '']
                if not blank_note.empty:
                    blank_amt = blank_note[detail_amt_col].abs().sum()
                    pt.add_text_slide("无备注记录风险提示", [
                        f"• 无备注记录数：{len(blank_note):,} 条（占全部 {len(blank_note)/max(len(detail),1):.1%}）",
                        f"• 涉及偏差金额：{blank_amt:,.0f} 元",
                        "• 无备注 → 无法归因 → 无法追责 → 只能靠猜",
                        "• 这是全部诊断里最该先解决的一环：数据质量不解决，"
                        "后面所有分析都建立在猜测上",
                    ])
            if blank_amt is None:
                # v43.156：缺备注列时也出页，说明「本项无法评估」而非静默消失
                pt.add_text_slide("无备注记录风险提示（本期无法评估）", [
                    "• 明细中未找到「备注」或「备注原因」列，无法统计无备注占比",
                    "• 无备注记录是归因可靠性的前置条件，建议优先补齐",
                    "• 请确认导出时「完整偏差明细」包含备注字段",
                ])

            pt.add_section("四、结论与行动")

            # 8c. 明细抽样（v43.156 新增，让执行层能落到明细）
            if detail_amt_col:
                top_detail = detail.reindex(detail[detail_amt_col].abs().sort_values(ascending=False).index).head(15)
                dcols = [c for c in ['物料编码', '物料名称', '车间', '偏差数量', '偏差率(%)', detail_amt_col]
                         if c in top_detail.columns]
                rows = [[str(r.get(c, ''))[:16] for c in dcols] for _, r in top_detail.iterrows()]
                pt.add_table_slide("偏差最大明细 Top15", dcols, rows,
                                   col_widths=[2.2, 3.2, 1.2, 1.4, 1.4, 1.8])
        else:
            # ---- 简明版：只保留给管理层看的结论（v43.156）----
            # v43.156 修复：旧版简明版从不调用 add_section()，toc_entries 恒为空
            # → add_toc_slide() 直接 return → 目录页压根没生成，预留的第 2 页
            # 留成一片空白。现给简明版也建章节，目录才有内容、才不是空白页。
            pt.add_section("核心指标")
            pt.add_section("核心结论")
            pt.add_section("行动建议")

            pt.add_text_slide("核心结论", [
                f"• 本期偏差记录 {total_rows:,} 条，正偏差（多耗）{pos_cnt:,} 条 / "
                f"{pos_amount:,.0f} 元",
                f"• 负偏差（少耗）{neg_cnt:,} 条 / {neg_amount:,.0f} 元",
                f"• 净偏差 {net_amount:,.0f} 元"
                + ("（正偏差，即整体多耗，需关注）" if net_amount > 0
                   else "（负偏差，即整体少耗，需关注）" if net_amount < 0 else "（基本持平）"),
                f"• 备注覆盖率 {note_rate:.1%}"
                + ("，归因基础较好" if note_rate >= 0.8 else "，偏低，将直接影响归因可靠性"),
            ])

        # 9. 行动建议
        pt.add_text_slide("分阶段改进行动", [
            "【立即行动（1周内）】",
            "• 强制补录无备注记录",
            "• 完善系统无定额物料",
            "• 核查领用记录异常",
            "",
            "【短期优化（1月内）】",
            "• 优化批次分摊逻辑",
            "• 加强设备维护",
            "• 规范工艺执行",
            "",
            "【中期建设（3月内）】",
            "• 替代料净偏差自动抵消",
            "• 上线实时预警看板",
            "• 实现系统领用与实际双重校验"
        ])

        # 9b. 数据质量卡（v43.156 新增，必出页）
        # 放行动建议之前：先说清「这份数据本身可不可信」，再谈怎么办。
        # 只依赖已算出的 total_rows / note_rate，任何数据下都能出。
        if is_pro:
            _dq_rows = [
                ("记录总数", f"{total_rows:,} 条", "分析口径内的偏差记录总量"),
                ("备注覆盖率", f"{note_rate:.1%}",
                 "≥80% 归因可靠 / <50% 归因基本靠猜"),
                ("有备注记录", f"{int(total_rows * note_rate):,} 条", "可用于根因分析的样本量"),
                ("无备注记录", f"{int(total_rows * (1 - note_rate)):,} 条",
                 "这部分无法归因，等于账面数字在裸奔"),
            ]
            pt.add_text_slide("数据质量卡（先看这份数据能不能信）", [
                "【记录规模】",
                "• 记录总数：%s（%s）" % (_dq_rows[0][1], _dq_rows[0][2]),
                "",
                "【归因可行性】",
                "• 备注覆盖率：%s（%s）" % (_dq_rows[1][1], _dq_rows[1][2]),
                "• 有备注：%s / 无备注：%s" % (_dq_rows[2][1], _dq_rows[3][1]),
                "",
                "【结论】",
                ("• 覆盖率达标，本报告的归因结论可直接用于决策"
                 if note_rate >= 0.8 else
                 "• 覆盖率偏低，本报告的「原因分布」只能当线索看，"
                 "不能直接用来定责 —— 先补备注，再谈考核"),
            ])

        # 10. 目标量化
        pt.add_text_slide("预期效果与目标量化", [
            f"• 偏差金额降低30%（当前净偏差 {net_amount:,.0f} 元）",
            f"• 备注覆盖率从 {note_rate:.1%} 提升至 80% 以上",
            "• 异常响应时效从月度缩短至日度",
            "• 消除无备注高偏差记录，建立真实数据基础"
        ])

        # ---- 目录页：内容加完后生成，再搬到第 2 页（v43.156）----
        # v43.156 修复：旧版在所有内容加完才 add_toc_slide()，目录落在**最后一页**
        #   （源码注释自认「本版就放在末尾」），用户得翻到第 10 页才看到目录。
        # 现用 _move_slide_to 重排 <p:sldIdLst> 把它搬到封面之后（索引 1）。
        #
        # 注意：一开始想「预留一个空白占位页再填内容」，实测这会留下一张真空白页
        # （占位页 add 了但没填任何 shape，目录搬走后它还留在第 3 页），
        # 等于凭空多一页且第 3 页全白。故改为**不预留占位**，目录直接搬到索引 1。
        if pt.toc_entries:
            pt.add_toc_slide()
            built_idx = len(pt.prs.slides) - 1     # 实际生成的目录页（当前末页）
            target_idx = 1                        # 封面之后
            if built_idx == target_idx:
                pass                             # 已在正确位置，无需搬
            elif _move_slide_to(pt.prs, built_idx, target_idx):
                _safe_log(log_cb, "目录页已置顶到第 2 页", "info")
            else:
                _safe_log(log_cb, "目录页搬运失败，目录将保留在末尾", "warning")

        # 兜底：清掉任何「一个 shape 都没有」的空白页（防止将来新增占位逻辑再留空白）
        _drop_blank_slides(pt)

        pt.save(output_path)
        n_slides = len(pt.prs.slides)
        _safe_log(log_cb, "%s报告 v2 已生成：%s (共%d页)" % (
            "专业版" if is_pro else "简明版", output_path, n_slides), "info")
        return True
    except Exception as e:
        # v43.156：这里的 log_cb 调用是旧代码的致命 bug —— 传 1 个参数给 (msg, level)
        # 签名的回调，本身抛 TypeError 把原始异常顶掉。现改用 _safe_log 并传 level。
        _safe_log(log_cb, "生成失败：%s" % (e,), "error")
        import traceback
        _safe_log(log_cb, traceback.format_exc(limit=5), "error")
        traceback.print_exc()
        return False
