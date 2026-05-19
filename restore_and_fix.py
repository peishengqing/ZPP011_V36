# -*- coding: utf-8 -*-
import subprocess

# 从git获取正确编码的文件
result = subprocess.run(['git', 'show', '6456975:gui/events.py'], capture_output=True)
content = result.stdout
# 去除BOM
if content.startswith(b'\xef\xbb\xbf'):
    content = content[3:]

# 解码为字符串
text = content.decode('utf-8')

# 1. 添加列名清理（在 dev_df.empty 检查之后）
old1 = 'raise ValueError("偏差明细工作表为空")'
new1 = '''raise ValueError("偏差明细工作表为空")
        # 列名清理
        dev_df.columns = [str(c).strip().replace(' ', '') for c in dev_df.columns]'''
text = text.replace(old1, new1)

# 2. 添加日期列映射（在生成唯一ID之前）
old2 = '# 生成唯一ID'
new2 = '''# 日期列映射
        if '订单开始日期' in audit_df.columns and '订单日期' not in audit_df.columns:
            audit_df['订单日期'] = audit_df['订单开始日期'].astype(str).str[:10]
        elif '订单日期' not in audit_df.columns:
            audit_df['订单日期'] = ''
        # 生成唯一ID'''
text = text.replace(old2, new2)

# 写回文件
with open(r'E:\zpp011_dev\模块化脚本\gui\events.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Restored and fixed')
