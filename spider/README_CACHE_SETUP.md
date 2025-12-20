# 设置 Hugging Face 模型缓存到 I 盘

如果 C 盘空间不足，可以将模型下载到 I 盘。

## 方法一：设置系统环境变量（推荐，永久生效）

1. 右键"此电脑" → "属性" → "高级系统设置"
2. 点击"环境变量"
3. 在"用户变量"或"系统变量"中添加：

```
变量名: HF_HOME
变量值: I:\huggingface_cache

变量名: TRANSFORMERS_CACHE
变量值: I:\huggingface_cache

变量名: HF_HUB_CACHE
变量值: I:\huggingface_cache
```

4. 重启命令行/Python 环境

## 方法二：在代码中设置（临时生效）

测试脚本已经自动设置了缓存目录到 `I:\huggingface_cache`。

如果需要在其他脚本中使用，可以在代码开头添加：

```python
import os
os.environ["HF_HOME"] = r"I:\huggingface_cache"
os.environ["TRANSFORMERS_CACHE"] = r"I:\huggingface_cache"
os.environ["HF_HUB_CACHE"] = r"I:\huggingface_cache"
```

## 验证设置

运行以下命令检查当前缓存位置：

```bash
python -m spider.check_cache_location
```

## 注意事项

- 确保 I 盘有足够空间（每个模型可能需要几百 MB 到几 GB）
- 如果 I 盘路径不存在，程序会自动创建
- 设置环境变量后需要重启 Python 环境才能生效

