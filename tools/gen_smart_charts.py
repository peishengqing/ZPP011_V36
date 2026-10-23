#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
gen_smart_charts.py — ZPP011 交互式 ECharts 图表生成器（CLI 入口）
===================================================================
薄壳：把表格数据文件 + 图表配置 JSON 交给「smart-charts」技能渲染成交互式
HTML 图表。本文件**不含任何图表逻辑**：解析、聚合、统计、渲染全部由技能的
scripts/cli.py 完成（技能的硬约束：MUST 走 CLI 工作流，不要自写脚本替代）。

smart-charts 是**用户级技能**，不在本仓库内，运行时到用户技能目录里定位，
不硬编码绝对路径：
    1) ~/.workbuddy/skills/smart-charts/scripts/cli.py
    2) ~/.codebuddy/skills/smart-charts/scripts/cli.py
找不到时给出可操作的提示并以退出码 2 退出（不崩溃、不静默）。

技能 CLI 的 stdout 是 JSON（多图模式为 {"charts":[...], "summary":{...}}，
--profile 模式为画像对象），本脚本解析后打印人类可读摘要。

用法:
    # 1) 先只做数据画像（只读不落盘，用于决定出什么图）
    python tools/gen_smart_charts.py \
        --input "E:/ZPP011导出文件原数据/ZPP011_20261001-20261023.xlsx" \
        --charts-file charts.json \
        --output-dir "./out_charts" \
        --profile-only

    # 2) 批量出图
    python tools/gen_smart_charts.py \
        --input "E:/ZPP011导出文件原数据/ZPP011_20261001-20261023.xlsx" \
        --sheet "Data" \
        --charts-file "C:/Temp/zpp011_charts.json" \
        --output-dir "./out_charts" \
        --work-dir "./out_charts/_tmp"

charts.json 每项（由调用方按数据画像自己写）：
    {"type": "bar",
     "title": "各车间组件物料数 Top10",
     "x_axis": "生产管理员描述",
     "y_axis": "数量_定额",
     "transform_code": "result = df.groupby('生产管理员描述')['数量_定额'].count().reset_index()"}

注意：列名会被技能规范化（转小写、特殊字符→_，中文保留），配置里必须引用
规范化后的列名。
"""
import argparse
import glob
import json
import os
import subprocess
import sys


def find_skill_dir():
    """
    定位 smart-charts 技能根目录（含 SKILL.md 的那一层）。
    在用户技能目录下按 cli.py 定位，找不到返回 None。
    """
    home = os.path.expanduser("~")
    roots = [
        os.path.join(home, ".workbuddy", "skills"),
        os.path.join(home, ".codebuddy", "skills"),
    ]
    for root in roots:
        if not os.path.isdir(root):
            continue
        # 深度受限的通配，避免 skills 下无关目录过多时全盘扫描
        pattern = os.path.join(root, "smart-charts", "scripts", "cli.py")
        hits = sorted(glob.glob(pattern))
        if not hits:
            # 允许技能被多套放一层（如 skills/collection/smart-charts）
            hits = sorted(glob.glob(os.path.join(root, "*", "smart-charts", "scripts", "cli.py")))
        if hits:
            # cli.py 的上两级 = 技能根目录
            return os.path.dirname(os.path.dirname(os.path.abspath(hits[0])))
    return None


def parse_stdout_json(stdout):
    """
    从 stdout 中稳健截取 JSON 段并解析。
    子进程 stdout 前后可能混有噪声，故取第一个 '{' 到最后一个 '}' 再解析。
    解析失败返回 (None, 原始文本)。
    """
    text = stdout or ""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None, text
    try:
        return json.loads(text[start:end + 1]), text
    except json.JSONDecodeError as e:
        print(f"[WARN] 技能 stdout 的 JSON 解析失败：{e}", file=sys.stderr)
        return None, text


def dump_stdout_tail(text, lines=30):
    """JSON 解析失败时，打印 stdout 末尾若干行帮助定位"""
    tail = (text or "").splitlines()[-lines:]
    print("---- 技能 stdout 末尾 %d 行 ----" % len(tail), file=sys.stderr)
    for line in tail:
        print("  " + line, file=sys.stderr)
    print("--------------------------------", file=sys.stderr)


def err_message(err):
    """取错误描述文本：技能侧字段名是 error（字符串），部分分支用 message"""
    if not isinstance(err, dict):
        return str(err) if err else ""
    text = err.get("error") or err.get("message") or ""
    return text if isinstance(text, str) else str(text)


def report_error(payload, raw):
    """技能侧失败时，把结构化错误（含 suggestion）原样带出来"""
    err = (payload or {}).get("error") if isinstance(payload, dict) else None
    if isinstance(err, dict):
        print("[ERR] 技能执行失败", file=sys.stderr)
        print(f"       code_name : {err.get('code_name') or err.get('code')}", file=sys.stderr)
        print(f"       message   : {err_message(err)}", file=sys.stderr)
        details = err.get("details") or {}
        suggestion = details.get("suggestion")
        if suggestion:
            print(f"       suggestion: {suggestion}", file=sys.stderr)
        for key, val in details.items():
            if key != "suggestion":
                print(f"       {key}: {val}", file=sys.stderr)
        if not suggestion:
            dump_stdout_tail(raw)
    else:
        #顶层 error 直接是字符串描述
        print(f"[ERR] 技能执行失败：{err_message(err) or payload}", file=sys.stderr)
        dump_stdout_tail(raw)


def report_profile(prof):
    """打印数据画像摘要（--profile-only 模式）"""
    rows = prof.get("rows")
    cols = prof.get("columns")
    print(f"[画像] 行数={rows}  列数={len(cols) if isinstance(cols, list) else '未知'}")
    grain = prof.get("grain")
    if grain:
        print(f"       实体粒度: {grain}")
    if isinstance(cols, list):
        print("       列清单：")
        for col in cols:
            name = col.get("name")
            dtype = col.get("dtype")
            card = col.get("cardinality")
            miss = col.get("missing_rate")
            print(f"         - {name}（dtype={dtype}, 基数={card}, 缺失率={miss}）")
    signals = prof.get("signals")
    if signals:
        print("       候选洞察信号：")
        for sig in (signals if isinstance(signals, list) else [signals]):
            print(f"         - {sig}")
    rq = prof.get("row_quality")
    if rq:
        print(f"       行质量: {rq}")
    adv = prof.get("advisories")
    if adv:
        print("       口径提醒：")
        for item in adv:
            print(f"         - {item}")


def report_charts(payload, raw):
    """打印多图模式摘要"""
    charts = payload.get("charts") or []
    summary = payload.get("summary") or {}
    print(f"[出图] 共 {summary.get('total', len(charts))} 张"
          f"（成功 {summary.get('succeeded', 0)} / 失败 {summary.get('failed', 0)}）")
    for idx, c in enumerate(charts, 1):
        if not c.get("success"):
            err = c.get("error") or {}
            print(f"  [{idx}] 失败：{c.get('title') or '(无标题)'}")
            if isinstance(err, dict):
                print(f"       code_name : {err.get('code_name') or err.get('code')}")
                print(f"       message   : {err_message(err)}")
                details = err.get("details") or {}
            else:
                details = {}
                print(f"       message   : {err_message(err)}")
            suggestion = details.get("suggestion")
            if suggestion:
                print(f"       suggestion: {suggestion}")
            continue
        html_path = c.get("html_path")
        size = ""
        if html_path and os.path.exists(html_path):
            size = f"（{os.path.getsize(html_path):,} 字节）"
        print(f"  [{idx}] {c.get('title') or '(无标题)'}")
        print(f"       chart_type      : {c.get('chart_type')}")
        print(f"       html_path: {html_path}{size}")
        print(f"       源行数={c.get('source_rows')}  绘图行数={c.get('plotted_rows')}"
              f"  去重实体={c.get('unique_entities')}  数据行={c.get('data_rows')}")
        src = c.get("annotation_source")
        if src:
            print(f"       解读来源: {src}")
        for item in (c.get("advisories") or []):
            print(f"       [提醒] {item}")
    if not charts:
        print("       技能未返回任何图表条目。", file=sys.stderr)
        dump_stdout_tail(raw)


def main():
    ap = argparse.ArgumentParser(description="ZPP011 交互式 ECharts 图表生成器（走 smart-charts 技能 CLI）")
    ap.add_argument("--input", required=True, help="数据文件路径（xlsx/csv/tsv/json/txt）")
    ap.add_argument("--charts-file", default=None,
                    help="图表配置 JSON 路径（批量出图用；--profile-only 时可省略）")
    ap.add_argument("--output-dir", default=None, help="HTML 输出目录（--profile-only 时可省略）")
    ap.add_argument("--sheet", default=None, help="指定读哪个 sheet（默认第一个）")
    ap.add_argument("--profile-only", dest="profile_only", action="store_true",
                    help="只跑技能的数据画像，不出图、不落盘")
    ap.add_argument("--work-dir", default=None, help="中间目录（作为子进程工作目录，避免产物散落）")
    args = ap.parse_args()

    if not args.profile_only:
        missing = [name for name, val in (("--charts-file", args.charts_file),
                                          ("--output-dir", args.output_dir)) if not val]
        if missing:
            print(f"[ERR] 出图模式缺少必填参数：{'、'.join(missing)}（或改用 --profile-only）",
                  file=sys.stderr)
            sys.exit(2)

    skill_dir = find_skill_dir()
    if not skill_dir:
        print("[ERR] 未找到 smart-charts 技能，无法出图。", file=sys.stderr)
        print("       请先安装该技能，然后重试。检索命令：", file=sys.stderr)
        print('find "$HOME" -maxdepth 6 -type f -path "*smart-charts/scripts/cli.py"',
              file=sys.stderr)
        print("       期望位置：~/.workbuddy/skills/smart-charts/ 或 "
              "~/.codebuddy/skills/smart-charts/", file=sys.stderr)
        sys.exit(2)

    cli_py = os.path.join(skill_dir, "scripts", "cli.py")
    if not os.path.isfile(cli_py):
        print(f"[ERR] smart-charts 技能目录不完整，缺少 scripts/cli.py：{skill_dir}", file=sys.stderr)
        sys.exit(2)

    # 子进程命令：用当前解释器（sys.executable），不另找 python
    cmd = [sys.executable, cli_py, args.input]
    if args.sheet:
        cmd += ["--sheet", args.sheet]
    if args.profile_only:
        # 技能的 --profile 阶段只接受白名单参数，多传会被判为无效 flag 而报错
        cmd.append("--profile")
    else:
        cmd += ["--charts-file", args.charts_file, "--output-dir", args.output_dir]

    cwd = None
    if args.work_dir:
        os.makedirs(args.work_dir, exist_ok=True)
        cwd = args.work_dir

    print(f"[1/2] 调用 smart-charts 技能：{' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")

    # 技能侧 DEBUG/警告常走 stderr，转述出来但不当作错误
    if proc.stderr and proc.stderr.strip():
        print("---- 技能 stderr ----")
        print(proc.stderr.strip())
        print("--------------------")

    payload, raw = parse_stdout_json(proc.stdout)

    if payload is None:
        print("[ERR] 无法解析技能输出（可能是环境异常或技能崩溃）。", file=sys.stderr)
        dump_stdout_tail(raw)
        sys.exit(1)

    if isinstance(payload, dict) and payload.get("error"):
        report_error(payload, raw)
        sys.exit(1)

    print("[2/2] 完成")
    if args.profile_only:
        if proc.returncode != 0:
            report_error(payload, raw)
            sys.exit(1)
        report_profile(payload)
    else:
        report_charts(payload, raw)
        # 只要有图没成功，就以非零退出码让调用方/流水线能感知。
        # 技能批量模式下个别图失败时 returncode 可能仍为 0，故同时看 summary.failed。
        summary = payload.get("summary") or {}
        try:
            failed = int(summary.get("failed") or 0)
        except (TypeError, ValueError):
            failed = 0
        if proc.returncode != 0 or failed > 0:
            sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()