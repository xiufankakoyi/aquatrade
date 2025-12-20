"""
设置 Hugging Face 缓存到 I 盘
在运行测试脚本之前，先运行这个脚本设置环境变量
"""

import os
import sys

# 设置缓存目录到 I 盘
CACHE_DIR = r"I:\huggingface_cache"

# 设置环境变量（仅对当前 Python 进程有效）
os.environ["HF_HOME"] = CACHE_DIR
os.environ["TRANSFORMERS_CACHE"] = CACHE_DIR
os.environ["HF_HUB_CACHE"] = CACHE_DIR

print(f"✅ 已设置 Hugging Face 缓存目录为: {CACHE_DIR}")
print(f"\n注意：这个设置只在当前 Python 进程中有效")
print(f"如果要在所有 Python 程序中生效，请设置系统环境变量：")
print(f"  HF_HOME = {CACHE_DIR}")
print(f"  TRANSFORMERS_CACHE = {CACHE_DIR}")
print(f"  HF_HUB_CACHE = {CACHE_DIR}")

# 验证设置
try:
    from huggingface_hub import hf_hub_cache
    actual_cache = hf_hub_cache()
    print(f"\n当前实际使用的缓存目录: {actual_cache}")
except Exception as e:
    print(f"\n无法验证缓存目录: {e}")

