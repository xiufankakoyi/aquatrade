# 修复combined.py与cleaner.py和feishu_push.py的不一致问题

## 问题分析

通过对比三个文件的代码，我发现了以下关键差异导致输出结果不一致：

### 1. 输出目录不同
- **cleaner.py**: 输出文件到当前工作目录（默认位置）
- **combined.py**: 输出文件到数据所在目录（data_dir）

### 2. 错误处理不同
- **cleaner.py**: 使用更安全的数据访问方式，如`record.get('stockCode', '')`和try-except处理
- **combined.py**: 直接访问数据，如`stock_code = record['stockCode']`，可能导致键不存在错误

### 3. 数据访问方式不同
- **cleaner.py**: 对所有数据访问都使用get方法，确保即使键不存在也不会报错
- **combined.py**: 部分数据直接使用字典访问，可能导致KeyError

### 4. 功能整合问题
- **combined.py**: 整合了两个功能，但可能引入了新的问题

## 解决方案

### 1. 统一输出目录
修改combined.py的输出目录逻辑，使其与cleaner.py一致，或者明确指定输出目录。

### 2. 增强错误处理
将combined.py中的直接数据访问改为使用get方法，添加与cleaner.py相同的错误处理机制。

### 3. 统一数据处理逻辑
确保combined.py中的数据处理逻辑与cleaner.py完全一致，特别是：
- 龙虎榜数据处理
- 风险监控数据处理
- 涨停过滤数据处理
- AI提示词生成逻辑

### 4. 优化代码结构
- 移除重复代码
- 确保功能模块化
- 添加适当的注释

## 具体修改步骤

1. **修改输出目录逻辑**：统一文件输出位置
2. **增强错误处理**：添加try-except和get方法
3. **统一数据访问**：确保所有数据访问都使用安全方式
4. **测试验证**：运行修改后的代码，验证输出结果与cleaner.py和feishu_push.py一致

通过这些修改，我们可以确保combined.py的输出结果与cleaner.py和feishu_push.py完全一致，同时保持其整合功能的优势。