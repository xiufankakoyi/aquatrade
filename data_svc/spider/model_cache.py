"""
模型缓存模块 - 模型持久化存储
即使重新加载 test.py，模型也会保持加载状态
"""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from modelscope import snapshot_download

# 模型配置
MODEL_NAME = "qwen/Qwen2.5-1.5B-Instruct"
MODEL_CACHE_DIR = "I:/models_cache"

# 全局变量保存模型和tokenizer（持久化）
_tokenizer = None
_model = None

def get_model():
    """获取模型和tokenizer（仅在第一次调用时加载）"""
    global _tokenizer, _model
    
    if _tokenizer is None or _model is None:
        print("正在加载模型到显卡...")
        model_dir = snapshot_download(MODEL_NAME, cache_dir=MODEL_CACHE_DIR)
        _tokenizer = AutoTokenizer.from_pretrained(model_dir)
        _tokenizer.padding_side = "left"
        if _tokenizer.pad_token is None:
            _tokenizer.pad_token = _tokenizer.eos_token
        _model = AutoModelForCausalLM.from_pretrained(model_dir, device_map="auto", torch_dtype=torch.float16)
        print("模型加载完成！")
    else:
        print("使用已加载的模型（无需重新加载）")
    
    return _tokenizer, _model

