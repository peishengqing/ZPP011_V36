# gui/app.py 缩进错误手动修复指南

## 问题定位

**错误**：`IndentationError: unexpected indent` 在第324行附近

**根因**：
1. 第322行 `        from core.view_manager import ViewManager  # Task 012` 错误地在 `__init__` 方法内部（前面有8个空格缩进）
2. 应该作为模块导入在文件顶部
3. 第324行 `        self.audit_logger = AuditLogger()` 缩进可能不正确

## 修复步骤（手动操作）

### 步骤1：删除错误位置的导入

1. 用VS Code或任何文本编辑器打开 `E:\zpp011_dev\模块化脚本\gui\app.py`
2. 转到第322行（或搜索 `from core.view_manager import ViewManager`）
3. 如果这行前面有空格缩进（8个空格），**整行删除**

### 步骤2：在文件顶部添加导入

1. 在文件顶部找到其他 `from core.xxx import` 语句（通常在文件开头，第10-30行之间）
2. 在其中一行后面添加新行：
   ```python
   from core.view_manager import ViewManager  # Task 012
   ```
3. 保存文件

### 步骤3：修复第324行缩进

1. 找到第324行 `        self.audit_logger = AuditLogger()`
2. 确保这一行前面有**正好8个空格**（与 `self.task_manager = ...` 对齐）
3. 如果缩进不对，删除前面的空格，重新输入8个空格

### 步骤4：验证修复

在命令行运行：
```cmd
cd E:\zpp011_dev\模块化脚本
python main.py
```

如果程序能启动并显示GUI窗口，说明修复成功。

## 快速验证方法

在VS Code中：
1. 按 `Ctrl+Shift+P`
2. 输入 `Convert Indentation to Spaces`
3. 选择 `4`
4. 保存文件

这会统一整个文件的缩进为4空格，可以自动修复缩进不一致的问题。

## 常见问题

**Q: 如何找到文件顶部的导入区域？**
A: 搜索 `from core.` 或 `import `，通常在文件前50行内。

**Q: 如果删除第322行后程序仍报错？**
A: 可能还有其他缩进错误，查看错误信息中的行号，按相同方法修复。

**Q: 修复后运行提示其他错误？**
A: 将完整的错误信息发给我，我会继续帮助修复。