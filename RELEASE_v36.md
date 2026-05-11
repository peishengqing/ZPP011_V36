# 📦 ZPP011 v36 发布包

> 发布版本：v36
> 发布日期：2026-05-11
> 打包人：裴盛清

---

## 📁 推荐发布包目录结构

```
ZPP011_Analyzer_v36_Release/
├── main.py
├── requirements.txt
├── README_v36.md
├── DELIVERY_v36.md
├── FROZEN_v36.md
├── REGRESSION_CHECKLIST.md
│
├── gui/
│   ├── __init__.py
│   ├── app.py
│   ├── ui_builder.py
│   └── events.py
│
├── analysis/
│   ├── __init__.py
│   ├── analyzer.py
│   └── sheets/
│       ├── __init__.py
│       └── ...
│
├── domain/
│   └── alt_material/
│       ├── __init__.py
│       └── alt_manager.py
│
├── storage/
│   ├── __init__.py
│   └── storage.py
│
├── export/
│   └── ppt/
│       ├── __init__.py
│       └── ppt_generator.py
│
├── utils/
│   ├── __init__.py
│   └── helpers.py
│
├── config/
│   ├── __init__.py
│   ├── settings.py
│   └── paths.py
│
├── logger.py
└── exceptions.py
```

---

## 📄 requirements.txt

```
pandas>=1.5
openpyxl>=3.1
python-pptx>=0.6
numpy
```

---

## 🚀 安装与启动

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动程序

```bash
python main.py
```

---

## ✅ 上线前检查清单

- [ ] 冻结文件未修改
- [ ] `test_smoke.py` 冒烟测试通过
- [ ] 日志正常输出到 `temp\zpp011.log`
- [ ] Excel / PPT 可正常生成
- [ ] 界面启动无报错

---

## 📋 冒烟测试命令

```bash
cd E:\zpp011_dev\模块化脚本
python test_smoke.py
```

预期输出：
```
✅ logger OK
✅ exceptions OK
✅ config OK
✅ utils OK
✅ gui import OK
✅ analysis import OK
✅ 冒烟测试全部通过
```

---

## 🔖 Git 发布参考

```bash
# 打标签
git tag -a v36 -m "v36 正式发布：重构完成，工程级交付"

# 推送标签
git push origin v36

# 或生成 release note
git tag -l v36
```

### Release Note 模板

```markdown
## ZPP011 偏差分析器 v36

### 🎯 核心改进
- 完成模块化重构（gui/analysis/domain/storage/export/utils/config）
- 统一日志规范
- 完善异常体系
- 工程级交付文档

### 📦 发布内容
- 源码包
- 冒烟测试脚本
- 交付文档

### ✅ 质量保证
- 冒烟测试通过
- 冻结文件清单确认
- 回归检查清单完整
```

---

## 🔖 Git 发布命令

```bash
# 打标签
git tag -a v36-final -m "ZPP011 Analyzer v36 正式封板"

# 推送标签
git push origin v36-final
```

## 📋 Release Note 模板（可直接粘进 GitHub / GitLab）

```markdown
# ZPP011 偏差分析器 v36（正式封板）

## ✅ 版本状态
- 模块化完成
- 业务零修改
- 风险可控

## ✅ 核心特性
- 模块化目录结构
- 统一日志与异常体系
- 明确冻结边界

## ❌ 冻结内容
- 偏差率 / 金额计算
- 审核存储结构
- 替代料业务规则

## ✅ 使用方式
pip install -r requirements.txt
python main.py

## ✅ 回归检查
详见 REGRESSION_CHECKLIST.md
```

---

*此文件为 ZPP011 v36 交付物的一部分。*
