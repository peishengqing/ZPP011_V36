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
import time
import logging
import requests

logger = logging.getLogger("AIClient")

# ── Agnes AI 配置 ──────────────────────────────────────
AGNES_BASE_URL = "https://apihub.agnes-ai.com/v1"
AGNES_MODEL = "agnes-2.0-flash"
AGNES_API_KEY = ""  # 不硬编码！通过 'ai.api_key' 配置项或环境变量 AGNES_API_KEY 设置

# RPM 限制：20次/分钟 → 调用间隔至少 3.0 秒
MIN_CALL_INTERVAL = 3.0

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
        """获取 API Key：优先配置文件，其次环境变量，未配置时降级 Mock"""
        cfg = self._load_config()
        if cfg:
            try:
                key = cfg.get("ai.api_key", "")
                if key:
                    return key
            except Exception:
                pass
        import os
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

    # ── 真实 AI 调用 ────────────────────────────────

    def _rate_limit(self):
        """速率控制：首次调用不等待，后续调用间隔 ≥ MIN_CALL_INTERVAL 秒"""
        if self._last_call_time == 0:
            self._last_call_time = time.time()
            return
        elapsed = time.time() - self._last_call_time
        if elapsed < MIN_CALL_INTERVAL:
            time.sleep(MIN_CALL_INTERVAL - elapsed)
        self._last_call_time = time.time()

    def _call_agnes(self, user_message: str) -> dict:
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
            "model": AGNES_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.3,
            "max_tokens": 300,
        }

        response = requests.post(
            f"{AGNES_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=5,
        )

        if response.status_code == 429:
            # 触发速率限制，等待后重试一次
            logger.warning("Agnes AI 速率限制，等待 10 秒后重试...")
            time.sleep(10)
            response = requests.post(
                f"{AGNES_BASE_URL}/chat/completions",
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
        批量审核多条记录（一次 API 调用处理多条，大幅提速）。

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

            api_key = self._get_api_key()
            response = requests.post(
                f"{AGNES_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": AGNES_MODEL,
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
                logger.warning("Agnes AI 速率限制，等待 10 秒后重试...")
                time.sleep(10)
                response = requests.post(
                    f"{AGNES_BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": AGNES_MODEL,
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
                    raise RuntimeError("Agnes AI 速率限制，重试仍失败")

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
