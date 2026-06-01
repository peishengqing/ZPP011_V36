#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复 _show_audit_card 中的成本换算器代码块"""

with open('gui/event_handlers/table_events.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 旧代码块（从文件中精确复制）
old_code = '''        # 成本换算器（简化版，直接用偏差金额/偏差数量）
        try:
            # 获取偏差金额
            dev_amount_val = None
            for key in ["deviation_amount", "偏差金额"]:
                val = data.get(key)
                if val and str(val).strip() not in ("0", "-", ""):
                    try:
                        dev_amount_val = float(str(val).replace(",", ""))
                        break
                    except:
                        continue
            if dev_amount_val and abs(dev_amount_val) > 0.001:
                # 获取数量偏差（实际-定额）
                dev_qty_val = None
                for key in ["偏差数量", "数量偏差", "dev_qty"]:
                    val = data.get(key)
                    if val:
                        try:
                            dev_qty_val = float(val)
                            if abs(dev_qty_val) > 0.0001:
                                break
                        except:
                            continue
                if dev_qty_val and abs(dev_qty_val) > 0.0001:
                    # 单价 = 偏差金额绝对值 / 偏差数量绝对值
                    unit_price = abs(dev_amount_val) / abs(dev_qty_val)
                    # 单位
                    unit_name = ""
                    for key in ["单位", "组件单位", "unit"]:
                        val = data.get(key)
                        if val and str(val) not in ("nan", "None", ""):
                            unit_name = str(val)
                            break
                    if not unit_name:
                        unit_name = "单位"
                    sign_icon = "↑" if dev_amount_val > 0 else "↓"
                    # 直接显示
                    info += f"\\n💰 偏差金额：¥{dev_amount_val:,.2f} {sign_icon} ≈ {abs(dev_qty_val):.1f} {unit_name}（单价 ¥{unit_price:.2f}/{unit_name}）"
                else:
                    info += f"\\n💰 偏差金额：¥{dev_amount_val:,.2f}（数量偏差为0或缺失）"
        except Exception as e:
            info += f"\\n⚠️ 成本换算失败：{e}"'''

# 新代码块（裴哥给的）
new_code = '''        try:
            # 1. 获取偏差金额（兼容两种列名）
            dev_amount = None
            for key in ["deviation_amount", "偏差金额"]:
                val = data.get(key)
                if val and str(val).strip() not in ("0", "-", ""):
                    try:
                        dev_amount = float(str(val).replace(",", ""))
                        break
                    except:
                        continue
            if dev_amount is not None and abs(dev_amount) > 0.001:
                # 2. 获取数量偏差（实际-定额）
                dev_qty = None
                for key in ["偏差数量", "数量偏差", "dev_qty"]:
                    val = data.get(key)
                    if val:
                        try:
                            dev_qty = float(val)
                            if abs(dev_qty) > 0.0001:
                                break
                        except:
                            continue
                # 3. 获取单位
                unit = ""
                for key in ["单位", "组件单位", "unit"]:
                    val = data.get(key)
                    if val and str(val) not in ("nan", "None", ""):
                        unit = str(val)
                        break
                if not unit:
                    unit = "单位"
                # 4. 显示换算结果
                if dev_qty is not None and abs(dev_qty) > 0.0001:
                    unit_price = abs(dev_amount) / abs(dev_qty)
                    sign = "↑" if dev_amount > 0 else "↓"
                    info += f"\\n💰 偏差金额：¥{dev_amount:,.2f} {sign} ≈ {abs(dev_qty):.1f} {unit}（单价 ¥{unit_price:.2f}/{unit}）"
                else:
                    info += f"\\n💰 偏差金额：¥{dev_amount:,.2f}（数量偏差为0或缺失）"
        except Exception as e:
            info += f"\\n⚠️ 成本换算失败：{e}"'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('gui/event_handlers/table_events.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('✅ 替换成功')
else:
    print('❌ 未找到旧代码块')
    # 调试：找成本换算器位置
    idx = content.find('成本换算器')
    if idx >= 0:
        print('找到成本换算器，前后文：')
        print(repr(content[idx:idx+500]))
