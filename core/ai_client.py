# -*- coding: utf-8 -*-
# core/ai_client.py
"""
AI 客户端封装 — Agnes AI 真模型 + Mock 降级

支持两种模式：
  - 真实 AI：调用 Agnes AI (OpenAI 兼容接口)，制造业偏差智能审核
  - Mock 模式：本地规则判断，离线/网络异常时自动降级

Agnes AI: 免费，OpenAI 兼容，20 RPM 限制，无需绑卡充值
"""

import json
import os
import time
import logging
import requests

logger = logging.getLogger("AIClient")

# 导入本地模型路由
try:
    from model_router import select_model
except Exception:
    # 如果 project 目录下没有 model_router，使用默认选择（Agnes）
    def select_model(question, force_image=False):
        return "agnes-3.0-flash", "Agnes 3.0 Flash", "默认模型"

# ── 模型配置管理 ──────────────────────────────────────
# 从 WorkBuddy 的 models.json 读取所有模型的配置
def _get_all_models_config():
    """读取 WorkBuddy models.json 中所有模型的配置。

    返回 dict: {model_id: {"base_url", "model", "api_key"}}
    """
    fallback = {}
    try:
        models_path = os.path.join(os.path.expanduser("~"), ".workbuddy", "models.json")
        if not os.path.exists(models_path):
            return fallback
        with open(models_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = data if isinstance(data, list) else data.get("models", [])
        models_config = {}
        for m in entries:
            model_id = str(m.get("id", ""))
            if model_id:
                models_config[model_id] = {
                    "base_url": m.get("url", ""),
                    "model": model_id,
                    "api_key": m.get("apiKey") or m.get("api_key", ""),
                }
        return models_config
    except Exception as e:
        logger.warning("读取 WorkBuddy models.json 失败：%s", e)
        return fallback

MODELS_CONFIG = _get_all_models_config()

# ── Agnes AI 配置（向后兼容） ──────────────────────────
# 兜底默认值。运行时优先读取 WorkBuddy 的 models.json，使其跟随 WorkBuddy 侧配置。
# v43.258：models.json 里的条目已从 agnes-2.5-flash 换成 agnes-3.0-flash
#（512K 上下文 / 最大输出 65,536，长文与 HTML 生成都够用），解析逻辑同步改优先级，
#否则会因找不到 2.5-flash 而静默丢失 key → 整个 AI 审核实际在跑 Mock 降级。
AGNES_BASE_URL = "https://apihub.agnes-ai.cn/v1"
AGNES_MODEL = "agnes-3.0-flash"
AGNES_API_KEY = ""  # 不硬编码！优先从 WorkBuddy models.json 读取，其次 'ai.api_key' 配置项或环境变量 AGNES_API_KEY

# RPM 限制：20次/分钟 → 调用间隔至少 3.0 秒
MIN_CALL_INTERVAL = 3.0


def _resolve_agnes_config():
    """从 WorkBuddy 的 models.json 读取 Agnes 模型的端点/模型/密钥。

    返回 dict: {"base_url", "model", "api_key"}。
    选取优先级：agnes-3.0-flash > 任意 agnes-* 条目 > 模块常量兜底。
    文件不存在或读取失败时回退到上面的模块常量。
    """
    fallback = {
        "base_url": AGNES_BASE_URL,
        "model": AGNES_MODEL,
        "api_key": "",
    }
    try:
        models_path = os.path.join(os.path.expanduser("~"), ".workbuddy", "models.json")
        if not os.path.exists(models_path):
            return fallback
        with open(models_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = data if isinstance(data, list) else data.get("models", [])
        chosen = None
        # 1) 首选 3.0-flash（大输出，适合长文/HTML 生成）
        for m in entries:
            if str(m.get("id", "")) == "agnes-3.0-flash":
                chosen = m
                break
        # 2) 退而求其次：任意 agnes-* 条目（防止以后再换型号又静默丢 key）
        if chosen is None:
            for m in entries:
                if str(m.get("id", "")).startswith("agnes-"):
                    chosen = m
                    break
        if chosen is not None:
            return {
                "base_url": chosen.get("url") or fallback["base_url"],
                "model": chosen.get("id") or fallback["model"],
                "api_key": chosen.get("apiKey") or chosen.get("api_key") or "",
            }
    except Exception as e:
        logger.warning("读取 WorkBuddy models.json 失败，使用内置缺省配置：%s", e)
    return fallback

# ── 系统提示词 ─────────────────────────────────────────
SYSTEM_PROMPT = """你是一个制造业生产偏差审核专家，服务于云南达利食品有限公司。
你的任务是对 SAP 系统中的物料消耗偏差记录进行智能审核并给出建议。

审核规则：
1. 如果备注已清晰说明偏差原因（替代料、系统无定额、设备故障、BOM变更、配方调整、来料批次差异、盘点调整等），标记"合格"
2. 如果备注有内容但不够具体（太短、太模糊、无实质原因），标记"需改进"
3. 如果备注为空：
   - 偏差率 < 5%：标记"合格"
   - 5% ≤ 偏差率 < 10%：标记"需关注"
   - 偏差率 ≥ 10%：标记"需补备注"
4. 建议要具体、可操作，结合物料类型：
   - 包材类：设备换型废品、来料不良批次、灌装工艺异常、瓶坯变形
   - 原料类：配方调整、投料误差、水分含量差异、原料批次切换
   - 辅料类：添加比例波动、计量设备误差、辅料替换

输出格式：严格 JSON，不要包含其他文字
{"result": "合格|需关注|需改进|需补备注", "suggestion": "具体建议"}

建议控制在30-80字，用中文，语气专业客观。"""


class AIClient:
    """AI 审核客户端，支持 Agnes AI 真模型 + Mock 降级"""

    def __init__(self):
        self._config = None
        self._last_call_time = 0          # 速率控制
        self._total_calls = 0             # 统计
        self._mock_calls = 0
        self._models_config = MODELS_CONFIG.copy()

        # 解析 Agnes 端点/模型/密钥：优先跟随 WorkBuddy 的 models.json
        ag = _resolve_agnes_config()
        self._agnes_base_url = ag["base_url"]
        self._agnes_model = ag["model"]
        self._agnes_api_key = ag["api_key"]

    # ── 配置 ────────────────────────────────────────

    def _load_config(self):
        if self._config is not None:
            return self._config
        try:
            from core.config_manager import get_config_manager
            self._config = get_config_manager()
        except Exception:
            self._config = None
        return self._config

    def _get_api_key(self):
        """获取 API Key：优先 WorkBuddy models.json，其次项目配置，其次环境变量，未配置时降级 Mock"""
        # 1) WorkBuddy models.json 中 Agnes 模型（优先 agnes-3.0-flash）的 key
        if self._agnes_api_key:
            return self._agnes_api_key
        # 2) 项目配置文件 ai.api_key
        cfg = self._load_config()
        if cfg:
            try:
                key = cfg.get("ai.api_key", "")
                if key:
                    return key
            except Exception:
                pass
        # 3) 环境变量 AGNES_API_KEY
        env_key = os.environ.get("AGNES_API_KEY", "")
        if env_key:
            return env_key
        logger.warning("未配置 AI API Key，使用 Mock 降级模式")
        return ""

    def _use_real_ai(self):
        """判断是否使用真实 AI"""
        cfg = self._load_config()
        if cfg:
            try:
                # 显式配置为 false 才关闭真 AI
                use_mock = cfg.get("ai.use_mock_ai", False)
                if use_mock:
                    return False
            except Exception:
                pass
        return True  # 默认使用真 AI，失败自动降级 Mock

    # ── Mock 降级 ───────────────────────────────────

    def _get_mock_result(self, text, dev_rate):
        """本地规则降级（真 AI 不可用时使用）"""
        self._mock_calls += 1
        remark_str = str(text).strip() if text is not None else ""
        if remark_str in ('nan', 'NaN', 'None', 'none', ''):
            abs_rate = abs(dev_rate)
            if abs_rate < 5:
                return {"result": "合格", "suggestion": "小偏差(5%以内)，可接受，无需特别说明"}
            elif abs_rate < 10:
                return {"result": "需关注", "suggestion": f"偏差{abs_rate:.1f}%，建议确认原因"}
            else:
                direction = "超耗" if dev_rate > 0 else "少耗"
                return {"result": "需补备注",
                        "suggestion": f"{direction}{abs_rate:.1f}%，建议检查BOM用量或核实实际消耗"}
        if any(kw in remark_str for kw in ["超耗", "少耗", "损耗", "替代", "变更", "设备", "配方"]):
            return {"result": "合格", "suggestion": "备注清晰"}
        if len(remark_str) < 5:
            return {"result": "需改进", "suggestion": "备注过短（小于5个字），建议补充详细原因"}
        return {"result": "需改进", "suggestion": "建议明确偏差原因（如超耗/少耗/替代/变更）"}

    # ── 模型路由与统一调用 ──────────────────────────

    def _get_model_config(self, model_id: str) -> dict:
        """获取指定模型的配置。"""
        if model_id in self._models_config:
            cfg = self._models_config[model_id]
            if cfg["api_key"]:
                return cfg

        # 对于 Agnes 模型，使用自己的配置
        if model_id == "agnes-3.0-flash":
            return {
                "base_url": self._agnes_base_url,
                "model": self._agnes_model,
                "api_key": self._agnes_api_key,
            }

        # 兜底：找不到配置也返回一个（可能调用失败）
        return {"base_url": "", "model": model_id, "api_key": ""}

    def _call_model(self, model_id: str, messages: list, system_prompt: str,
                    temperature: float = 0.3, max_tokens: int = 300) -> dict:
        """
        调用指定模型，返回结果。
        用于审核场景，返回 JSON 格式结果。
        """
        # 获取模型配置
        cfg = self._get_model_config(model_id)
        if not cfg["base_url"] or not cfg["api_key"]:
            raise RuntimeError(f"模型 {model_id} 未配置 API Key 或 Base URL")

        # 构造消息
        payload = {
            "model": cfg["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": messages[-1]["content"]},  # 只取最后一条用户消息
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        api_key = cfg["api_key"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        def _post():
            return requests.post(
                f"{cfg['base_url']}/chat/completions",
                headers=headers,
                json=payload,
                timeout=10,
            )

        for attempt in range(2):
            try:
                response = _post()
                if response.status_code == 429:
                    time.sleep(10)
                    continue
                if response.status_code == 500:
                    time.sleep(15)
                    continue
                break
            except Exception as e:
                if "connection" in str(e).lower() or "timeout" in str(e).lower():
                    time.sleep(10)
                    continue
                raise

        if response.status_code == 429 or response.status_code == 500:
            raise RuntimeError(f"模型 {model_id} 请求失败，状态码 {response.status_code}")

        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()

        # 尝试提取 JSON
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            result = json.loads(content[json_start:json_end])
            return {
                "result": result.get("result", "需关注"),
                "suggestion": result.get("suggestion", content),
            }
        else:
            return {"result": "需关注", "suggestion": content[:200]}

    def _call_agnes(self, user_message: str) -> dict:
        """
        调用 AI 模型（基于路由自动选择）
        返回 {"result": "...", "suggestion": "..."} 或抛异常
        """
        self._rate_limit()

        # 1. 自动路由选择模型
        model_id, model_name, reason = select_model(user_message)
        logger.info(f"AIClient 模型路由: {reason} → {model_name} ({model_id})")

        # 2. 构建提示词
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        try:
            # 3. 使用路由后的模型调用
            result = self._call_model(
                model_id=model_id,
                messages=messages,
                system_prompt=SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=300,
            )
            logger.debug(f"AI 审核结果: {result['result']} | {result['suggestion'][:50]}...")
            return result

        except Exception as e:
            logger.warning(f"AI 调用失败 ({e})，降级 Mock")
            remark = str(user_message[:200])
            return self._get_mock_result(remark, dev_rate=0)

        """
        调用 Agnes AI Chat Completions API
        返回 {"result": "...", "suggestion": "..."} 或抛异常
        """
        self._rate_limit()

        api_key = self._get_api_key()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._agnes_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.3,
            "max_tokens": 300,
        }

        response = requests.post(
            f"{self._agnes_base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=5,
        )

        if response.status_code == 429:
            # 触发速率限制，等待后重试一次
            logger.warning("Agnes AI 速率限制，等待 10 秒后重试...")
            time.sleep(10)
            response = requests.post(
                f"{self._agnes_base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=5,
            )
            if response.status_code == 429:
                raise RuntimeError("Agnes AI 速率限制，重试仍失败")

        response.raise_for_status()
        data = response.json()

        # 解析响应
        content = data["choices"][0]["message"]["content"].strip()

        # 尝试提取 JSON（模型可能在 JSON 前后加了文字）
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            result = json.loads(content[json_start:json_end])
            return {"result": result.get("result", "需关注"),
                    "suggestion": result.get("suggestion", content)}
        else:
            # 模型没返回 JSON，把原始响应当建议
            return {"result": "需关注", "suggestion": content[:200]}

    def generate_text(self, system_prompt: str, user_prompt: str,
                      max_tokens: int = 32000, timeout: int = 180) -> str:
        """通用文本生成（归藏 AI 设计报告用）：返回模型原始输出文本。

        与 _call_agnes 的区别：
          · 不强制 JSON 输出，原样返回（HTML 由调用方自行提取）；
          · max_tokens / timeout 都按长输出调（一整份 15 页 HTML 约 2~4 万 token）；
          · 没有 key 时直接抛异常，**不走 Mock 降级** —— Mock 对「生成设计」毫无意义，
            静默降级只会让用户以为拿到了 AI 设计，实际是本地兜底（调用方自己决定回退）。
        """
        self._rate_limit()

        api_key = self._get_api_key()
        if not api_key:
            raise RuntimeError(
                "未配置 AI API Key：请在 WorkBuddy models.json 配置 agnes-3.0-flash，"
                "或在项目配置 ai.api_key / 环境变量 AGNES_API_KEY 中提供。"
            )

        payload = {
            "model": self._agnes_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,   # 设计类任务要多样性，比审核的 0.3 高
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._agnes_base_url}/chat/completions"

        def _post():
            return requests.post(url, headers=headers, json=payload, timeout=timeout)

        response = _post()
        if response.status_code == 429:
            logger.warning("Agnes AI 速率限制，等待 10 秒后重试...")
            time.sleep(10)
            response = _post()
            if response.status_code == 429:
                raise RuntimeError("Agnes AI 速率限制，重试仍失败")
        # 5xx 瞬时错误（实测 agnes 端偶发 520，一次端到端白丢 4 分钟）：退避 15s 重试一次
        if 500 <= response.status_code < 600:
            logger.warning("Agnes AI 服务端错误 %s，等待 15 秒后重试...", response.status_code)
            time.sleep(15)
            response = _post()

        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if not content or not content.strip():
            raise RuntimeError("Agnes AI 返回空内容")
        self._total_calls += 1
        return content

    # ── 构建提示 ────────────────────────────────────

    def _build_user_message(self, context: dict, dev_rate: float) -> str:
        """根据上下文构建给 AI 的审核请求"""
        remark = str(context.get("remark", "")).strip()
        if remark in ('nan', 'None', 'none', ''):
            remark = "（无备注）"

        parts = ["请审核以下生产偏差记录：", ""]

        # 物料信息
        mat_code = context.get("物料编码", "")
        mat_name = context.get("物料描述", "") or context.get("物料名称", "")
        mat_cat = context.get("物料大类", "") or context.get("物料类型", "")
        if mat_code:
            mat_line = f"物料：{mat_code}"
            if mat_name:
                mat_line += f" {mat_name}"
            if mat_cat:
                mat_line += f"（{mat_cat}）"
            parts.append(mat_line)

        # 工厂/车间
        factory = context.get("工厂", "") or context.get("工厂名称", "")
        workshop = context.get("车间", "")
        if factory:
            loc = factory
            if workshop:
                loc += f" / {workshop}"
            parts.append(f"位置：{loc}")

        # 订单
        order_no = context.get("流程订单", "") or context.get("生产订单", "")
        if order_no:
            parts.append(f"订单：{order_no}")

        # 偏差数据
        abs_rate = abs(dev_rate)
        direction = "超耗" if dev_rate > 0 else ("少耗" if dev_rate < 0 else "持平")
        parts.append(f"偏差率：{direction} {abs_rate:.1f}%")

        dev_amount = context.get("偏差金额", 0) or context.get("总偏差金额(含税)", 0)
        dev_qty = context.get("偏差数量", 0)
        if dev_amount:
            try:
                parts.append(f"偏差金额：{float(dev_amount):.2f} 元")
            except Exception:
                pass
        if dev_qty:
            try:
                parts.append(f"偏差数量：{float(dev_qty):.2f}")
            except Exception:
                pass

        # 备注
        parts.append("")
        parts.append(f"当前备注：{remark}")

        # ── 历史高频原因参考 ──
        try:
            mat_code = context.get("物料编码", "")
            factory = context.get("工厂", "") or context.get("工厂名称", "")
            workshop = context.get("车间", "")
            if mat_code:
                from core.history_freq import format_history_hint
                hint = format_history_hint(mat_code, factory, workshop)
                if hint:
                    parts.append("")
                    parts.append(hint)
        except Exception:
            pass

        parts.append("")
        parts.append("请输出 JSON：")

        return "\n".join(parts)

    # ── 公共接口 ────────────────────────────────────

    def audit(self, text, dev_rate=0.0):
        """
        审核一条偏差记录（兼容旧接口，内部可能走批量模式）。

        参数：
            text: 备注文本或 context dict
            dev_rate: 偏差率（%）

        返回：
            {"result": "合格|需关注|需改进|需补备注", "suggestion": "..."}
        """
        if isinstance(text, dict):
            context = text
            dev_rate = context.get("dev_rate", dev_rate)
        else:
            context = {"remark": text}

        return self._audit_internal(context, dev_rate)

    def audit_batch(self, items: list) -> list:
        """
        批量审核多条记录（一次 API 调用处理多条，大幅提速，使用路由模型）。

        参数：
            items: [{"context": dict, "dev_rate": float}, ...]

        返回：
            [{"result": "合格|...", "suggestion": "..."}, ...] 与 items 一一对应
        """
        n = len(items)
        if n == 0:
            return []
        if n == 1:
            return [self._audit_internal(items[0]["context"], items[0]["dev_rate"])]

        self._total_calls += 1

        if not self._use_real_ai():
            return [self._get_mock_result(i["context"].get("remark", ""), i["dev_rate"]) for i in items]

        try:
            # 构建批量提示词
            lines = [f"请审核以下 {n} 条生产偏差记录，对每条逐一判断。", ""]
            for idx, item in enumerate(items, 1):
                ctx = item["context"]
                dev = item["dev_rate"]
                remark = str(ctx.get("remark", "")).strip()
                if remark in ('nan', 'None', 'none', ''):
                    remark = "（无备注）"

                abs_rate = abs(dev)
                direction = "超耗" if dev > 0 else ("少耗" if dev < 0 else "持平")

                lines.append(f"--- 记录{idx} ---")
                mat = ctx.get("物料编码", "")
                if mat:
                    name = ctx.get("物料描述", "") or ""
                    cat = ctx.get("物料大类", "") or ""
                    lines.append(f"物料：{mat} {name}{'（'+cat+'）' if cat else ''}")
                factory = ctx.get("工厂", "") or ctx.get("工厂名称", "")
                workshop = ctx.get("车间", "")
                if factory:
                    lines.append(f"位置：{factory}{' / '+workshop if workshop else ''}")
                order = ctx.get("流程订单", "") or ctx.get("生产订单", "")
                if order:
                    lines.append(f"订单：{order}")
                lines.append(f"偏差率：{direction} {abs_rate:.1f}%")
                dev_amount = ctx.get("偏差金额", 0)
                if dev_amount:
                    try:
                        lines.append(f"偏差金额：{float(dev_amount):.2f} 元")
                    except Exception:
                        pass
                lines.append(f"当前备注：{remark}")
                lines.append("")

            lines.append("对每条记录返回 JSON 数组，格式严格：")
            lines.append('[{"record":1,"result":"合格|需关注|需改进|需补备注","suggestion":"..."}, ...]')
            lines.append("不要包含其他文字，只输出 JSON 数组。")

            user_msg = "\n".join(lines)
            self._rate_limit()

            # 使用路由后的模型
            model_id, model_name, reason = select_model(f"审核{len(items)}条偏差记录")
            logger.info(f"AuditBatch 模型路由: {reason} → {model_name} ({model_id})")

            cfg = self._get_model_config(model_id)

            if not cfg["base_url"] or not cfg["api_key"]:
                raise RuntimeError(f"模型 {model_id} 未配置")

            response = requests.post(
                f"{cfg['base_url']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {cfg['api_key']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": cfg["model"],
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000,
                },
                timeout=20,
            )

            if response.status_code == 429:
                logger.warning(f"{model_name} 速率限制，等待 10 秒后重试...")
                time.sleep(10)
                response = requests.post(
                    f"{cfg['base_url']}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {cfg['api_key']}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": cfg["model"],
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_msg},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 2000,
                    },
                    timeout=45,
                )
                if response.status_code == 429:
                    raise RuntimeError(f"{model_name} 速率限制，重试仍失败")

            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"].strip()

            # 提取 JSON 数组
            arr_start = content.find("[")
            arr_end = content.rfind("]") + 1
            if arr_start >= 0 and arr_end > arr_start:
                results = json.loads(content[arr_start:arr_end])
                # 确保顺序正确
                mapped = []
                for i in range(n):
                    found = None
                    for r in results:
                        if r.get("record") == i + 1:
                            found = r
                            break
                    if found:
                        mapped.append({"result": found.get("result", "需关注"),
                                       "suggestion": found.get("suggestion", "")})
                    else:
                        mapped.append(self._get_mock_result(
                            items[i]["context"].get("remark", ""), items[i]["dev_rate"]
                        ))
                return mapped
            else:
                raise json.JSONDecodeError("No JSON array found", content, 0)

        except Exception as e:
            logger.warning(f"批量审核异常 ({e})，降级逐条 Mock")
            return [self._get_mock_result(i["context"].get("remark", ""), i["dev_rate"]) for i in items]

    def _audit_internal(self, context: dict, dev_rate: float) -> dict:
        """内部审核入口，先尝试真实 AI，失败降级 Mock"""
        self._total_calls += 1

        if not self._use_real_ai():
            remark = context.get("remark", "")
            return self._get_mock_result(remark, dev_rate)

        try:
            user_msg = self._build_user_message(context, dev_rate)
            result = self._call_agnes(user_msg)
            logger.debug(f"Agnes AI 审核结果: {result['result']} | {result['suggestion'][:50]}...")
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Agnes AI 返回非标准 JSON ({e})，降级 Mock")
            remark = context.get("remark", "")
            return self._get_mock_result(remark, dev_rate)

        except (requests.Timeout, requests.ConnectionError) as e:
            logger.warning(f"Agnes AI 网络不可达 ({e})，降级 Mock")
            remark = context.get("remark", "")
            return self._get_mock_result(remark, dev_rate)

        except Exception as e:
            logger.warning(f"Agnes AI 调用异常 ({e})，降级 Mock")
            remark = context.get("remark", "")
            return self._get_mock_result(remark, dev_rate)

    def get_stats(self) -> dict:
        """获取调用统计"""
        return {
            "total_calls": self._total_calls,
            "mock_fallbacks": self._mock_calls,
            "real_calls": self._total_calls - self._mock_calls,
        }
