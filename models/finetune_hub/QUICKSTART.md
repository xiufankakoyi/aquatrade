# 快速启动指南

## 安装步骤

1. **进入项目目录**
   ```bash
   cd llm-finetuning-hub
   ```

2. **安装依赖**
   ```bash
   npm install
   ```

3. **启动开发服务器**
   ```bash
   npm run dev
   ```

4. **打开浏览器**
   访问 `http://localhost:3000`

## 功能使用

### 1. 数据整理面板
- 在文本区域输入或粘贴 JSONL 格式的训练数据
- 点击"验证格式"检查数据格式是否正确
- 点击"洗数"按钮清理多余空格和特殊字符

### 2. 训练配置面板
- 使用滑动条调整 Learning Rate、Batch Size
- 选择 LoRA Rank（4, 8, 16, 32, 64）
- 切换 Gradient Checkpointing 和 Aim Logging 开关
- 点击"开始训练"启动训练（当前为模拟）

### 3. 提示词对比实验室
- 左侧输入原始 Prompt，右侧输入微调后的 Prompt
- 点击"开始对比"查看两个模型的输出差异
- 启用"高亮差异"查看详细的差异对比

### 4. 可视化监控
- 确保 Aim Stack 服务运行在 `http://localhost:43800`
- 在 IFrame 中查看训练指标和可视化图表
- 可以修改 URL 连接到不同的 Aim 实例

## 注意事项

- 当前版本使用模拟数据，需要连接实际后端 API
- 确保 Aim Stack 服务已启动才能查看可视化
- 所有训练操作目前为模拟，需要实现实际 API 集成

## 下一步

1. 实现后端 API 集成
2. 添加 WebSocket 支持实时训练进度
3. 集成实际的模型推理 API

