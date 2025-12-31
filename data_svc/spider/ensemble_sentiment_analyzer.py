"""
情感分析模块：使用 RoBERTa-wwm 模型 + 关键词规则
使用填空法：构造"文本，后市看[MASK]。"让模型预测填"涨"还是"跌"
"""

from typing import Optional, Tuple, List, Dict
from pathlib import Path

# 模型配置（仅使用 RoBERTa-wwm）
ENSEMBLE_MODELS = [
    {
        "name": "RoBERTa-wwm",
        "model_id": "hfl/chinese-roberta-wwm-ext",
        "weight": 1.0
    },
]

# 填空提示模板
MASK_TEMPLATE = "{}，后市看{}。"

# 🔴 看涨关键词库 (Bullish Slang)
# 这些词在股民口中通常代表机会，即便模型可能认为是负面的（比如"洗盘"、"暴力"）
BULLISH_KEYWORDS = [
    # 动作类
    "洗盘", "建仓", "加仓", "补仓", "重仓", "锁仓", "抄底", "封板", "起飞", "反攻", "抢筹", "拉升",
    # 状态类
    "量价齐升", "趋势", "支撑", "多头", "金叉", "翻倍", "底部", "缩量", "突破", "走强", "安全",
    # 情绪类
    "主力", "庄家", "北向", "牛市", "利好", "信心", "机会", "期待", "看好", "不买后悔", "真香"
]

# 🟢 看跌关键词库 (Bearish Slang)
# 这些词代表风险，哪怕模型觉得是正面的（比如"核按钮"听起来很有力，但其实是大跌）
BEARISH_KEYWORDS = [
    # 动作类
    "出货", "派发", "减仓", "清仓", "割肉", "止损", "跑路", "砸盘", "核按钮", "撤退", "跳水",
    # 状态类
    "破位", "走弱", "死叉", "阴跌", "见顶", "放量下跌", "回调", "被套", "套牢", "垃圾", "亏损",
    # 情绪类
    "崩盘", "散户", "利空", "陷阱", "骗局", "完蛋", "销户", "大面", "A杀", "坑爹"
]

# ⚪ 中性关键词库 (Neutral Slang)
# 这些词通常只是描述事实，不带情绪，用来防止模型瞎猜
NEUTRAL_KEYWORDS = [
    # 状态类
    "横盘", "震荡", "整理", "磨底", "观望", "等信号", "持币", "窄幅", "平开", "波动"
]


class EnsembleSentimentAnalyzer:
    """情感分析器（RoBERTa-wwm + 关键词规则）"""
    
    def __init__(self, models_config: Optional[List[Dict]] = None):
        """
        初始化集成分析器
        
        Args:
            models_config: 模型配置列表，如果为 None 则使用默认配置
        """
        self.models_config = models_config or ENSEMBLE_MODELS
        self.loaded_models = []
        # 将关键词作为成员变量，方便访问
        self.BULLISH_KEYWORDS = BULLISH_KEYWORDS
        self.BEARISH_KEYWORDS = BEARISH_KEYWORDS
        self.NEUTRAL_KEYWORDS = NEUTRAL_KEYWORDS
        self._load_models()
    
    def _load_models(self):
        """加载所有模型（使用 fill-mask pipeline）"""
        try:
            from transformers import pipeline, AutoTokenizer, AutoModelForMaskedLM
            import torch
            import warnings
        except ImportError:
            print("[WARN] transformers 库未安装，无法使用集成模型")
            return
        
        # 抑制模型权重未初始化的警告
        warnings.filterwarnings("ignore", message=".*were not initialized from the model checkpoint.*")
        warnings.filterwarnings("ignore", message=".*return_all_scores.*")
        
        # 检测GPU可用性
        use_gpu = torch.cuda.is_available()
        device_id = 0 if use_gpu else -1
        if use_gpu:
            print(f"[GPU] 检测到 CUDA，将使用 GPU 加速（设备: {torch.cuda.get_device_name(0)}，fp16）")
        else:
            print(f"[CPU] 未检测到 CUDA，将使用 CPU（fp32，速度较慢）")
        
        print(f"正在加载 {len(self.models_config)} 个模型（填空模式）...")
        for model_info in self.models_config:
            try:
                torch_dtype = torch.float16 if use_gpu else torch.float32
                
                # 加载 fill-mask pipeline
                fill_mask = pipeline(
                    "fill-mask",
                    model=model_info["model_id"],
                    device=device_id,
                    torch_dtype=torch_dtype
                )
                
                # 加载 tokenizer 和 model 用于获取 token id
                tokenizer = AutoTokenizer.from_pretrained(model_info["model_id"])
                model = AutoModelForMaskedLM.from_pretrained(
                    model_info["model_id"],
                    torch_dtype=torch_dtype
                )
                if use_gpu:
                    model = model.to(device_id)
                model.eval()
                
                # 获取"涨"和"跌"的 token id
                token_ids_up = tokenizer.encode("涨", add_special_tokens=False)
                token_ids_down = tokenizer.encode("跌", add_special_tokens=False)
                
                # 通常是一个 token，但为了安全取第一个
                token_id_up = token_ids_up[0] if token_ids_up else None
                token_id_down = token_ids_down[0] if token_ids_down else None
                
                self.loaded_models.append({
                    **model_info,
                    "fill_mask": fill_mask,
                    "tokenizer": tokenizer,
                    "model": model,
                    "token_id_up": token_id_up,
                    "token_id_down": token_id_down,
                    "device_id": device_id
                })
                print(f"  ✅ {model_info['name']} 加载成功 ({'GPU' if use_gpu else 'CPU'})")
                print(f"      Token ID - 涨: {token_id_up}, 跌: {token_id_down}")
            except Exception as e:
                print(f"  ⚠️  {model_info['name']} 加载失败: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        if self.loaded_models:
            print(f"✅ 成功加载 {len(self.loaded_models)} 个模型，准备使用填空法情感分析")
        else:
            print("❌ 没有成功加载任何模型")
    
    def analyze_batch(self, texts: List[str], batch_size: int = 128, use_keywords: bool = False) -> List[Tuple[float, str]]:
        """
        真正的 GPU 批量并行处理 (Batch Processing)
        
        Args:
            texts: 待分析的文本列表
            batch_size: 批量大小，默认 128
            use_keywords: 是否先检查关键词
        
        Returns:
            List[Tuple[float, str]]: 每个文本的 (bullish_bearish_score, method)
        """
        if not texts:
            return []
        
        # 结果占位符
        results = [None] * len(texts)
        
        # --- 第一层：关键词快速过滤 (CPU 极速处理) ---
        # 记录哪些索引已经被关键词解决了，哪些需要丢给 GPU
        need_model_indices = []
        
        for i, text in enumerate(texts):
            if not text or not isinstance(text, str):
                results[i] = (0.0, "fallback_neutral")
                continue
            
            # 关键词判断
            if use_keywords:
                text_lower = text.lower()
                # 简单粗暴的关键词匹配
                if any(k in text_lower for k in self.BEARISH_KEYWORDS):
                    results[i] = (-1.0, "keyword_bearish")
                    continue
                if any(k in text_lower for k in self.BULLISH_KEYWORDS):
                    results[i] = (1.0, "keyword_bullish")
                    continue
            
            # 如果没命中关键词，加入待推理列表
            need_model_indices.append(i)

        # 如果全部都被关键词解决了，直接返回
        if not need_model_indices:
            return results

        # --- 第二层：RoBERTa 批量推理 (GPU 并行) ---
        if not self.loaded_models:
            for idx in need_model_indices:
                results[idx] = (0.0, "roberta_fallback_no_models")
            return results

        model_info = self.loaded_models[0]
        tokenizer = model_info.get("tokenizer")
        model = model_info.get("model")
        token_id_up = model_info.get("token_id_up")
        token_id_down = model_info.get("token_id_down")
        device_id = model_info.get("device_id", -1)
        
        if tokenizer is None or model is None:
            for idx in need_model_indices:
                results[idx] = (0.0, "roberta_fallback_no_classifier")
            return results
        
        # 准备所有待推理的 Prompt
        prompts = [MASK_TEMPLATE.format(texts[i][:200], tokenizer.mask_token) for i in need_model_indices]
        
        import torch
        
        # 按 Batch Size 切分进行推理
        total_batches = (len(prompts) + batch_size - 1) // batch_size
        
        print(f"🚀 GPU启动: 处理 {len(prompts)} 条数据，共 {total_batches} 个 Batch...")

        for batch_start in range(0, len(prompts), batch_size):
            batch_end = min(batch_start + batch_size, len(prompts))
            batch_prompts = prompts[batch_start:batch_end]
            batch_indices = need_model_indices[batch_start:batch_end]  # 对应的原始索引
            
            try:
                # 1. 批量 Tokenize (padding=True 是关键，把短句子补齐到和长句子一样)
                inputs = tokenizer(batch_prompts, return_tensors="pt", padding=True, truncation=True, max_length=256)
                
                if device_id >= 0:
                    inputs = {k: v.to(device_id) for k, v in inputs.items()}
                
                with torch.no_grad():
                    # 2. 批量推理
                    outputs = model(**inputs)
                    logits = outputs.logits  # Shape: [batch_size, seq_len, vocab_size]
                
                # 3. 批量提取 [MASK] 位置的概率
                mask_token_id = tokenizer.mask_token_id
                input_ids = inputs["input_ids"]  # Shape: [batch_size, seq_len]
                
                # 找到每个样本中 [MASK] 的位置
                batch_size_actual = input_ids.shape[0]
                
                for batch_idx in range(batch_size_actual):
                    # 找到当前样本中 MASK token 的位置
                    mask_positions = (input_ids[batch_idx] == mask_token_id).nonzero(as_tuple=True)[0]
                    
                    if len(mask_positions) > 0:
                        # 取第一个 MASK 位置（通常只有一个）
                        mask_pos = mask_positions[0].item()
                        
                        # 获取该位置的 logits
                        mask_logits = logits[batch_idx, mask_pos, :]
                        
                        # 计算 softmax
                        probs = torch.softmax(mask_logits, dim=-1)
                        
                        if token_id_up is not None and token_id_down is not None:
                            prob_up = probs[token_id_up].item()
                            prob_down = probs[token_id_down].item()
                        else:
                            prob_up = 0.0
                            prob_down = 0.0
                        
                        # 计算分数
                        if prob_up + prob_down > 0:
                            score = (prob_up - prob_down) / (prob_up + prob_down)
                        else:
                            score = 0.0
                    else:
                        score = 0.0
                    
                    # 填回结果列表
                    original_idx = batch_indices[batch_idx]
                    results[original_idx] = (score, "roberta_mask")

            except Exception as e:
                print(f"⚠️ Batch {batch_start // batch_size + 1}/{total_batches} 出错: {e}")
                import traceback
                traceback.print_exc()
                # 出错回退
                for idx in batch_indices:
                    results[idx] = (0.0, "batch_error")

        return results
    
    def analyze(self, text: str, use_keywords: bool = False) -> Tuple[float, str]:
        """
        使用 RoBERTa-wwm 模型 + 关键词规则分析情感
        
        Args:
            text: 待分析的文本
            use_keywords: 是否先检查关键词（默认 False，避免反讽误判）
        
        Returns:
            Tuple[float, str]: (bullish_bearish_score, method)
            - bullish_bearish_score: -1.0（看空）到 +1.0（看多）的浮点数
            - method: "keyword_bearish" / "keyword_bullish" / "roberta_mask" / "fallback_neutral"
        """
        if not text or not isinstance(text, str):
            return 0.0, "fallback_neutral"
        
        # 第一层：关键词强制规则（可选，默认禁用，避免反讽误判）
        if use_keywords:
            text_lower = text.lower()
            for keyword in BEARISH_KEYWORDS:
                if keyword in text_lower:
                    return -1.0, "keyword_bearish"
            
            for keyword in BULLISH_KEYWORDS:
                if keyword in text_lower:
                    return 1.0, "keyword_bullish"
        
        # 第二层：RoBERTa-wwm 模型分析（填空法）
        if not self.loaded_models:
            return 0.0, "roberta_fallback_no_models"
        
        model_info = self.loaded_models[0]
        fill_mask = model_info.get("fill_mask")
        tokenizer = model_info.get("tokenizer")
        model = model_info.get("model")
        token_id_up = model_info.get("token_id_up")
        token_id_down = model_info.get("token_id_down")
        device_id = model_info.get("device_id", -1)
        
        if fill_mask is None or tokenizer is None or model is None:
            return 0.0, "roberta_fallback_no_classifier"
        
        try:
            import torch
            
            # 构造提示："文本，后市看[MASK]。"
            prompt = MASK_TEMPLATE.format(text[:200], tokenizer.mask_token)  # 限制长度避免超长
            
            # 直接使用模型计算 token 概率（更准确）
            if token_id_up is not None and token_id_down is not None:
                inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
                if device_id >= 0:
                    inputs = {k: v.to(device_id) for k, v in inputs.items()}
                
                with torch.no_grad():
                    outputs = model(**inputs)
                    logits = outputs.logits
                    
                    # 找到 [MASK] 位置
                    mask_token_id = tokenizer.mask_token_id
                    mask_positions = (inputs["input_ids"] == mask_token_id).nonzero(as_tuple=True)[1]
                    
                    if len(mask_positions) > 0:
                        mask_pos = mask_positions[0].item()
                        mask_logits = logits[0, mask_pos, :]
                        
                        # 计算 softmax
                        probs = torch.softmax(mask_logits, dim=-1)
                        
                        prob_up = probs[token_id_up].item()
                        prob_down = probs[token_id_down].item()
                    else:
                        prob_up = 0.0
                        prob_down = 0.0
            else:
                # 回退到 fill-mask pipeline
                mask_results = fill_mask(prompt, top_k=100)
                prob_up = 0.0
                prob_down = 0.0
                
                for result in mask_results:
                    token_str = result.get("token_str", "").strip()
                    score = float(result.get("score", 0.0))
                    
                    if token_str == "涨":
                        prob_up = score
                    elif token_str == "跌":
                        prob_down = score
            
            # 计算情感分数：归一化概率差
            if prob_up + prob_down > 0:
                # 归一化到 [-1, 1]
                final_score = (prob_up - prob_down) / (prob_up + prob_down)
            else:
                final_score = 0.0
            
            return final_score, "roberta_mask"
        except Exception as e:
            import traceback
            traceback.print_exc()
            return 0.0, "roberta_fallback_error"


# 全局实例（延迟加载）
_global_analyzer: Optional[EnsembleSentimentAnalyzer] = None


def get_ensemble_analyzer() -> Optional[EnsembleSentimentAnalyzer]:
    """获取全局情感分析器实例（单例模式）"""
    global _global_analyzer
    if _global_analyzer is None:
        _global_analyzer = EnsembleSentimentAnalyzer()
    return _global_analyzer


def calculate_sentiment_ensemble(
    text: str,
    use_keywords: bool = False
) -> Tuple[float, str]:
    """
    使用 RoBERTa-wwm 模型 + 关键词规则计算情感分数（便捷函数）
    
    Args:
        text: 待分析的文本
        use_keywords: 是否先检查关键词（默认 False，避免反讽误判）
    
    Returns:
        Tuple[float, str]: (bullish_bearish_score, method)
    """
    analyzer = get_ensemble_analyzer()
    if analyzer is None:
        return 0.0, "roberta_unavailable"
    return analyzer.analyze(text, use_keywords=use_keywords)

