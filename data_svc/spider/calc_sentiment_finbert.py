"""
使用 FinBERT 中文金融情感模型 + 股吧黑话词典暴力修正。
混合策略：优先匹配黑话关键词，匹配不到则使用模型预测。

【优化点】
1. 引入 StockSlangMatcher：解决 "吃肉"(涨)、"关灯吃面"(跌) 等模型听不懂的黑话。
2. 保持原有的显存管理和单例模式。
"""

from pathlib import Path
from typing import List, Optional, Tuple, Dict
import threading
import pandas as pd
from transformers import pipeline

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None

MAX_TEXT_LEN = 512

# ==================== 1. 股吧黑话词典 (人工规则) ====================
class StockSlangMatcher:
    """
    用于捕捉模型无法理解的股圈黑话。
    规则优先级高于 BERT 模型。
    """
    def __init__(self):
        # 正面词库 (Positive)
        self.pos_keywords = [
            "涨停", "大涨", "飞", "启动", "利好", "吃肉", "舒服", "龙头", 
            "满仓", "加仓", "抄底", "牛市", "连板", "起飞", "主升浪", 
            "大阳线", "红盘", "数钱", "给力", "看多", "封板", "妖股", 
            "跨年", "翻倍", "强势", "拉升", "涨涨", "不卖"
        ]
        # 负面词库 (Negative)
        self.neg_keywords = [
            "跌停", "大跌", "暴跌", "崩盘", "跳水", "垃圾", "骗子", 
            "割肉", "被套", "套住", "利空", "出货", "吃面", "关灯", 
            "完蛋", "凉凉", "退市", "清仓", "止损", "大阴线", "绿", 
            "地板", "瀑布", "坑人", "快跑", "要崩", "诱多", "废了"
        ]
    
    def match(self, text: str) -> Tuple[Optional[str], Optional[float]]:
        """
        返回: (label, score) 如果命中规则
        返回: (None, None) 如果未命中
        """
        if not isinstance(text, str):
            return None, None
            
        text = text.lower()
        
        # 简单判定：谁的关键词多就归谁，或者命中即返回
        # 这里采用命中即返回的高置信度策略
        for kw in self.pos_keywords:
            if kw in text:
                return "Positive", 0.999  # 人工规则置信度给满
                
        for kw in self.neg_keywords:
            if kw in text:
                return "Negative", 0.999
                
        return None, None

# ==================== 2. 模型管理器 (保持不变) ====================
class SentimentModelManager:
    _instance: Optional['SentimentModelManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._classifier: Optional[pipeline] = None
        self._model_lock = threading.Lock()
    
    def get_classifier(self):
        with self._model_lock:
            if self._classifier is None:
                print("正在加载 FinBERT 模型...")
                device = 0 if (TORCH_AVAILABLE and torch.cuda.is_available()) else -1
                self._classifier = pipeline(
                    "sentiment-analysis",
                    model="yiyanghkust/finbert-tone-chinese",
                    device=device,
                )
            return self._classifier

def chunk_list(items: List[str], batch_size: int) -> List[List[str]]:
    return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]

def main() -> None:
    # 路径配置：请确保这里指向正确的文件夹
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data/new" # 如果你的csv在 data/new，请修改这里为 data/new

    # 初始化匹配器
    slang_matcher = StockSlangMatcher()
    
    # 寻找CSV
    # 兼容 spider/data/*.csv 或 spider/data/new/*.csv，此处递归查找
    csv_files = sorted(data_dir.rglob("*.csv")) 
    
    if not csv_files:
        print(f"未在 {data_dir} 及其子目录下找到 .csv 文件")
        return

    # 初始化模型 (懒加载)
    model_manager = SentimentModelManager()
    
    print(f"找到 {len(csv_files)} 个文件，开始处理...")

    for csv_path in csv_files:
        print(f"\n>> 正在处理: {csv_path.name}")
        try:
            df = pd.read_csv(csv_path, encoding="utf-8-sig")
        except Exception as e:
            print(f"读取失败: {e}")
            continue

        if df.empty:
            continue

        # 初始化列
        if "sentiment_score" not in df.columns:
            df["sentiment_score"] = pd.NA
            df["sentiment_label"] = pd.NA

        # 找出需要计算的行（这里我们强制重新计算所有 Neutral 的行，或者全部重新计算）
        # 为了修复之前的错误结果，建议全部重新计算
        # 如果只想算空的，改为: mask = df["sentiment_score"].isna()
        print("   正在计算情绪 (混合策略: 规则优先 + 模型兜底)...")
        
        # 1. 提取所有文本
        # 注意：处理空值
        df['post_title'] = df['post_title'].fillna('')
        all_texts = df['post_title'].astype(str).tolist()
        
        # 结果容器
        final_labels = []
        final_scores = []
        
        # 待模型预测的文本批次
        to_predict_indices = []
        to_predict_texts = []
        
        # === 第一步：规则过滤 ===
        for idx, text in enumerate(all_texts):
            if not text.strip():
                final_labels.append("Neutral")
                final_scores.append(0.5)
                continue
                
            rule_label, rule_score = slang_matcher.match(text)
            if rule_label:
                # 命中规则
                final_labels.append(rule_label)
                final_scores.append(rule_score)
            else:
                # 未命中，标记为 None，稍后由模型填补
                final_labels.append(None)
                final_scores.append(None)
                to_predict_indices.append(idx)
                to_predict_texts.append(text[:MAX_TEXT_LEN])

        # === 第二步：模型预测剩余部分 ===
        if to_predict_texts:
            print(f"   命中黑话规则: {len(all_texts) - len(to_predict_texts)} 条")
            print(f"   模型需预测: {len(to_predict_texts)} 条")
            
            classifier = model_manager.get_classifier()
            batch_size = 32
            
            # 批量预测
            model_results = []
            for i, batch in enumerate(chunk_list(to_predict_texts, batch_size)):
                batch_res = classifier(batch)
                model_results.extend(batch_res)
                # 显存清理
                if TORCH_AVAILABLE and torch.cuda.is_available() and (i % 10 == 0):
                    torch.cuda.empty_cache()
            
            # 填回结果
            for local_idx, res in enumerate(model_results):
                global_idx = to_predict_indices[local_idx]
                final_labels[global_idx] = res['label']
                final_scores[global_idx] = res['score']
        else:
            print("   所有文本均命中黑话规则，无需加载模型。")

        # === 第三步：写回 DataFrame ===
        df['sentiment_label'] = final_labels
        df['sentiment_score'] = final_scores
        
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print("   ✅ 保存成功")

    print("\n处理完成！")

if __name__ == "__main__":
    main()