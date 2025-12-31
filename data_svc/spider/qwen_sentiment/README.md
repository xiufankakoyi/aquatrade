# Qwen 1.5B 情绪分析微调

这个文件夹包含了使用 Qwen2.5-1.5B-Instruct 模型进行股票评论情绪分析微调的完整流程。

## 文件说明

- `prepare_data.py` - 准备训练数据，将 test_data.json 转换为训练格式
- `train.py` - 训练 LoRA 微调模型（针对 8GB 显存优化）
- `test.py` - 测试脚本，对比基座模型和微调模型的性能
- `predict_lora.py` - 使用微调后的模型进行预测

## 使用流程

### 1. 准备训练数据

```bash
cd qwen_sentiment
python prepare_data.py
```

这会生成 `train_sentiment.jsonl` 文件。

### 2. 训练模型

```bash
python train.py
```

训练完成后，LoRA 权重会保存在 `./qwen_sentiment_lora/` 目录。

### 3. 测试模型

```bash
python test.py
```

这会对比基座模型（使用 v10 Prompt）和微调模型的准确率。

### 4. 使用模型预测

```bash
python predict_lora.py
```

## 配置说明

- **模型路径**: `MODEL_PATH` 在 `train.py` 中配置
- **LoRA 输出**: `./qwen_sentiment_lora/`（相对于当前文件夹）
- **测试数据**: `../test_data.json`（在上级目录）

## 训练参数（8GB 显存优化）

- `per_device_train_batch_size=2`
- `gradient_accumulation_steps=8`
- `gradient_checkpointing=True`
- `max_seq_length=512`
- `fp16=True`

