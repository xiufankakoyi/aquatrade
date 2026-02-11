# LLM Fine-tuning Hub

一个现代化的 LLM 微调实验控制台，使用 React + Tailwind CSS 构建。

## 功能特性

### 📊 数据整理面板
- JSONL 格式的文本编辑器
- 实时格式验证
- 数据清洗功能（去除多余空格和特殊字符）
- 数据统计信息

### ⚙️ 训练配置面板
- **核心参数控制**：
  - Learning Rate 滑动条（1e-6 到 1e-3）
  - LoRA Rank 选择（4, 8, 16, 32, 64）
  - Batch Size 滑动条（1 到 16）
- **监控开关**：
  - Gradient Checkpointing 开关
  - Aim Logging 开关
- **训练状态**：
  - 实时进度条
  - 训练状态反馈

### 🧪 提示词对比实验室
- 左右分屏布局（原始 Prompt vs 微调 Prompt）
- 并排显示模型输出
- Diff 模式高亮差异点
- 一键复制功能

### 📈 可视化监控
- Aim Stack UI 集成（IFrame）
- 可配置 Aim URL
- 刷新和新窗口打开功能

## 技术栈

- **React 18** - UI 框架
- **Tailwind CSS** - 样式框架
- **Lucide React** - 图标库
- **Vite** - 构建工具

## 安装和运行

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

## 项目结构

```
llm-finetuning-hub/
├── src/
│   ├── components/
│   │   ├── DataPreparationPanel.jsx    # 数据整理面板
│   │   ├── TrainingConfigPanel.jsx     # 训练配置面板
│   │   ├── PromptLab.jsx                # 提示词对比实验室
│   │   └── AimVisualization.jsx        # Aim 可视化
│   ├── App.jsx                          # 主应用组件
│   ├── main.jsx                         # 入口文件
│   └── index.css                        # 全局样式
├── index.html
├── package.json
├── vite.config.js
└── tailwind.config.js
```

## 设计风格

- **深色模式**：采用深色主题，类似 Vercel 和 Linear 的极简设计
- **响应式布局**：支持桌面和移动端
- **现代化 UI**：使用渐变、阴影和过渡动画

## API 集成

当前版本使用模拟数据。要连接实际后端 API，需要：

1. 在 `TrainingConfigPanel.jsx` 中实现实际的训练 API 调用
2. 在 `PromptLab.jsx` 中实现模型推理 API 调用
3. 配置 API 基础 URL

## 下一步开发

- [ ] 实现实际的后端 API 集成
- [ ] 添加 WebSocket 支持实时训练进度
- [ ] 增强 Diff 算法（使用专业 diff 库）
- [ ] 添加数据导入/导出功能
- [ ] 支持多实验对比

