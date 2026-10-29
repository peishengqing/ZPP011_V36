#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动模型选择器
基于问题语义匹配模型特征，自动推荐最合适的模型。
"""

from typing import Tuple


def select_model(question: str, force_image: bool = False) -> Tuple[str, str, str]:
    """
    根据问题自动选择最合适的模型

    参数:
        question: 用户的问题
        force_image: 是否强制使用视觉模型（如带图上传）

    返回:
        (model_id, model_name, reason)
    """
    q = question.lower()

    # 1. 强制视觉（有明确截图/图片）
    VISION_KEYWORDS = ["截图", "图片", "照片", "PPT", "PDF", "OCR", "看图", "识图"]
    if force_image or any(kw in q for kw in VISION_KEYWORDS):
        return "sensenova-6.8-flash-lite", "商汤日日新", "视觉任务，优先使用图像模型"

    # 2. 工具生成（生成文件/Excel）
    TOOL_KEYWORDS = ["生成", "创建", "Excel", "表格", "输出", "写入", "保存", "导出", "调用"]
    if any(kw in q for kw in TOOL_KEYWORDS):
        return "agnes-3.0-flash", "Agnes 3.0 Flash", "工具调用任务，使用全能模型"

    # 3. 翻译（有"翻译"，优先级高于多语言）
    if "翻译" in q:
        return "Sage-A1.5", "Sage-A1.5", "翻译任务，使用跨语言推理"

    # 4. 多语言（用英文写/多语言/跨语言 - 在没有翻译的前提下）
    MULTI_LANG_KEYWORDS = ["英文", "英语", "多语言", "跨语言", "国际化", "跨境", "电商", "客服"]
    if any(kw in q for kw in MULTI_LANG_KEYWORDS):
        return "Ling-3.1-flash", "Ling-3.1-flash", "多语言任务，使用多语言专家"

    # 5. 轻量总结（快速/简单/总结）
    LIGHT_KEYWORDS = ["快速", "简单", "总结", "算什么", "查一下"]
    if any(kw in q for kw in LIGHT_KEYWORDS):
        return "Atria-Dawn", "Atria-Dawn", "轻量任务，快速响应"

    # 6. 默认推理（分析/报告/逻辑/代码）
    INFERENCE_KEYWORDS = ["分析", "报告", "逻辑", "代码", "推理", "长文本", "解释", "数据", "计算"]
    if any(kw in q for kw in INFERENCE_KEYWORDS):
        return "glm-4.5", "GLM-4.5", "推理任务，使用中文推理最强模型"

    # 7. 默认
    return "glm-4.5", "GLM-4.5", "默认选择：中文推理模型"
