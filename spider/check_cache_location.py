"""
检查当前 Hugging Face 缓存位置
"""

try:
    from huggingface_hub import hf_hub_cache
    cache_dir = hf_hub_cache()
    print(f"当前 Hugging Face 缓存目录: {cache_dir}")
except ImportError:
    print("huggingface_hub 未安装")
    try:
        from transformers.utils import hub
        cache_dir = hub.DEFAULT_CACHE_DIR
        print(f"当前 Transformers 缓存目录: {cache_dir}")
    except ImportError:
        print("transformers 未安装")

