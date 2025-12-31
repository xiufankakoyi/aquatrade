# 项目清理计划

## 📋 冗余文件清单

### 🔴 可以删除的文件（测试/调试脚本）

这些文件是临时测试或调试用的，可以安全删除：

1. **根目录测试文件**：
   - `test.py` - LanceDB 索引优化测试
   - `test1.py` - LanceDB 排序验证工具
   - `test2.py` - LanceDB Schema 修复工具
   - `test_backtest_performance.py` - 回测性能测试

2. **调试脚本**：
   - `auto_debug_backtest.py` - 自动调试脚本
   - `debug_backtest_playwright.py` - Playwright 调试
   - `debug_perf.py` - 性能调试
   - `debug_start.bat` - 调试启动脚本
   - `debug_streaming_backtest.py` - 流式回测调试

3. **分析脚本**：
   - `analyze_logs.py` - 日志分析（如果不再需要）

### 🟡 可以移动到 scripts/ 目录的文件

这些文件还有用，但应该整理到 scripts/ 目录：

1. **检查/诊断脚本**：
   - `check_db_backend.py` - 数据库后端检查（移动到 `scripts/`）

### 🟠 需要检查的文件

1. **可能的重复文件**：
   - `data_svc/spider/app.py` - 可能是旧的 app.py，需要检查是否还在使用
   - `core/strategies/1.py` - 测试文件，需要确认是否还需要

2. **示例文件**：
   - `examples/test_vectorized_strategy.py` - 如果只是示例，可以保留或移动到 docs/

### 🟢 可以合并的文档

`docs/` 目录下的文档可能有些内容重复：
- `PERFORMANCE_REVIEW_AND_REFACTORING.md` - 详细审查
- `REFACTORING_SUMMARY.md` - 摘要版本
- `OPTIMIZATION_COMPLETED.md` - 优化完成报告
- `STARTUP_FIX.md` - 启动修复报告

建议：保留详细版本，删除或合并摘要版本。

---

## 🗑️ 清理脚本

创建一个清理脚本来安全删除这些文件：

```python
# scripts/cleanup_redundant_files.py
"""
清理冗余文件和代码
"""
import os
from pathlib import Path

# 要删除的文件列表
FILES_TO_DELETE = [
    # 测试文件
    "test.py",
    "test1.py", 
    "test2.py",
    "test_backtest_performance.py",
    
    # 调试脚本
    "auto_debug_backtest.py",
    "debug_backtest_playwright.py",
    "debug_perf.py",
    "debug_start.bat",
    "debug_streaming_backtest.py",
    
    # 分析脚本（可选）
    # "analyze_logs.py",  # 如果不再需要
]

# 要移动的文件（从根目录移动到 scripts/）
FILES_TO_MOVE = {
    "check_db_backend.py": "scripts/check_db_backend.py",
}

# 要检查的文件（需要手动确认）
FILES_TO_CHECK = [
    "data_svc/spider/app.py",
    "core/strategies/1.py",
]

def main():
    project_root = Path(__file__).parent.parent
    
    print("=" * 60)
    print("项目清理工具")
    print("=" * 60)
    
    # 1. 删除文件
    print("\n[1] 删除冗余文件...")
    deleted_count = 0
    for file in FILES_TO_DELETE:
        file_path = project_root / file
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"  ✓ 已删除: {file}")
                deleted_count += 1
            except Exception as e:
                print(f"  ✗ 删除失败: {file} - {e}")
        else:
            print(f"  - 不存在: {file}")
    
    print(f"\n  总计删除: {deleted_count} 个文件")
    
    # 2. 移动文件
    print("\n[2] 移动文件到 scripts/ 目录...")
    moved_count = 0
    for src, dst in FILES_TO_MOVE.items():
        src_path = project_root / src
        dst_path = project_root / dst
        
        if src_path.exists():
            try:
                # 确保目标目录存在
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 如果目标文件已存在，询问是否覆盖
                if dst_path.exists():
                    response = input(f"  目标文件已存在: {dst}，是否覆盖？(y/n): ")
                    if response.lower() != 'y':
                        print(f"  - 跳过: {src}")
                        continue
                
                src_path.rename(dst_path)
                print(f"  ✓ 已移动: {src} -> {dst}")
                moved_count += 1
            except Exception as e:
                print(f"  ✗ 移动失败: {src} - {e}")
        else:
            print(f"  - 不存在: {src}")
    
    print(f"\n  总计移动: {moved_count} 个文件")
    
    # 3. 检查文件
    print("\n[3] 需要手动检查的文件:")
    for file in FILES_TO_CHECK:
        file_path = project_root / file
        if file_path.exists():
            print(f"  ⚠️  {file} - 需要确认是否还在使用")
        else:
            print(f"  - {file} - 不存在")
    
    print("\n" + "=" * 60)
    print("清理完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()
```

---

## 📝 代码冗余检查

### 1. 重复的导入

检查是否有重复的导入语句（已在代码中优化）。

### 2. 未使用的函数

需要检查以下文件是否有未使用的函数：
- `server/app.py` - 可能有未使用的路由
- `server/visualization_api.py` - 可能有未使用的方法
- `data_svc/database/optimized_data_query.py` - 可能有未使用的方法

### 3. 重复的 app.py

`data_svc/spider/app.py` 可能是旧的 Flask 应用，需要确认：
- 是否还在使用？
- 是否可以删除？
- 或者应该移动到 `examples/` 目录？

---

## ✅ 清理步骤

1. **备份项目**（重要！）
   ```bash
   git commit -am "Before cleanup"
   git tag backup-before-cleanup
   ```

2. **运行清理脚本**
   ```bash
   python scripts/cleanup_redundant_files.py
   ```

3. **手动检查**
   - 检查 `data_svc/spider/app.py` 是否还在使用
   - 检查 `core/strategies/1.py` 是否还需要
   - 合并或删除重复的文档

4. **测试**
   - 确保项目仍然可以正常启动
   - 确保所有功能正常

5. **提交更改**
   ```bash
   git add .
   git commit -m "Clean up redundant files and code"
   ```

---

## 📊 预期清理效果

- **删除文件数**: ~10 个
- **移动文件数**: ~1 个
- **减少代码行数**: ~500-1000 行
- **项目结构**: 更清晰，更容易维护

---

## ⚠️ 注意事项

1. **不要删除**：
   - `scripts/` 目录下的脚本（这些是有用的工具）
   - `examples/` 目录下的示例（如果还有用）
   - 任何被其他文件导入的模块

2. **谨慎删除**：
   - 任何包含业务逻辑的文件
   - 任何可能在未来用到的工具脚本

3. **建议保留**：
   - `scripts/remove_debug_logs.py` - 有用的工具
   - `scripts/` 目录下的其他脚本 - 都是有用的工具

