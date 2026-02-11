# GPU 利用率优化指南

## 问题诊断

如果 GPU 占用率只有 8%，可能的原因：

1. **Batch Size 太小** - 当前默认是 2，对于 1.5B 模型来说太小
2. **数据加载瓶颈** - `dataloader_num_workers=0` 导致数据加载阻塞训练
3. **Gradient Accumulation 步数太多** - 减少了实际的计算频率
4. **模型太小** - 1.5B 模型计算量相对较小

## 已实施的优化

### 1. 自动增加 Batch Size
- 代码会自动将 batch size 从 2 增加到最多 8（如果显存允许）
- 有效 batch size = batch_size × gradient_accumulation_steps

### 2. 多进程数据加载
- GPU 模式：`dataloader_num_workers=4`
- CPU 模式：`dataloader_num_workers=0`
- 使用 `pin_memory=True` 加速数据传输

### 3. 减少 Gradient Accumulation
- 从 8 步减少到 4 步
- 增加实际的计算频率

### 4. GPU 监控
- 实时显示 GPU 显存使用情况
- 训练日志中包含 GPU 信息

## 进一步优化建议

### 如果 GPU 占用率仍然很低：

1. **手动增加 Batch Size**
   - 在训练配置面板中设置更大的 batch size（如 8 或 16）
   - 注意：需要足够的显存

2. **关闭 Gradient Checkpointing**
   - 虽然会占用更多显存，但可以提高 GPU 利用率
   - 在训练配置面板中关闭此选项

3. **增加序列长度**
   - 当前 `max_seq_length=512`
   - 如果数据较长，可以增加到 1024（需要更多显存）

4. **检查数据加载速度**
   - 确保数据文件在 SSD 上
   - 考虑使用更快的存储

## 监控 GPU 使用情况

### 方法 1: 使用 nvidia-smi
```bash
# Windows (PowerShell)
nvidia-smi -l 1

# 查看实时 GPU 使用率
```

### 方法 2: 通过 API
```bash
# 获取训练状态（包含 GPU 信息）
curl http://localhost:5001/api/train/status
```

### 方法 3: 查看训练日志
训练过程中会打印 GPU 显存使用情况：
```
Epoch 1.00 | Loss: 0.5 | GPU: 2.3/3.5GB
```

## 预期 GPU 占用率

对于 1.5B 模型：
- **Batch Size 2**: ~10-20% GPU 占用
- **Batch Size 4**: ~30-50% GPU 占用
- **Batch Size 8**: ~60-80% GPU 占用
- **Batch Size 16**: ~80-95% GPU 占用

## 注意事项

1. **显存限制**：增加 batch size 会增加显存占用
2. **训练速度**：更大的 batch size 通常意味着更快的训练（在显存允许的情况下）
3. **模型质量**：batch size 对最终模型质量影响较小，主要影响训练速度

## 故障排除

如果 GPU 占用率仍然很低：

1. **检查模型是否在 GPU 上**
   ```python
   import torch
   print(torch.cuda.is_available())
   print(next(model.parameters()).device)
   ```

2. **检查数据加载速度**
   - 如果数据加载是瓶颈，GPU 会等待数据
   - 增加 `dataloader_num_workers` 可能有助于解决

3. **检查是否有其他进程占用 GPU**
   ```bash
   nvidia-smi
   ```

4. **尝试更大的 Batch Size**
   - 在训练配置中手动设置更大的值
   - 观察显存使用情况，找到最佳值




