"""
改进的情感分析模块：双重判定逻辑
- 第一层：关键词强制规则（股吧黑话识别）
- 第二层：AI 模型兜底（Dianping 情感分析模型）
"""

from typing import Optional, Tuple
from pathlib import Path

# AI 模型配置（可在运行时覆盖）
# 使用 Dianping 模型，因为它最懂"散户的口语化吐槽"
DIANPING_MODEL_NAME = "uer/roberta-base-finetuned-dianping-chinese"

# 看空关键词（强制 -1）
BEARISH_KEYWORDS = [
    "垃圾", "跌停", "出货", "崩盘", "暴跌", "破位", "割肉", "套牢",
    "跑路", "暴雷", "退市", "st", "利空", "看空", "做空",
    "下跌", "回调", "调整", "阴跌", "破发", "破净", "亏损", "亏钱",
    "高估", "泡沫", "风险", "警告", "谨慎"
]

# 看多关键词（强制 +1）
BULLISH_KEYWORDS = [
    "涨停", "主力", "起飞", "拉升", "突破", "利好", "看多", "做多",
    "上涨", "反弹", "反转", "抄底", "建仓", "加仓", "持有", "买入",
    "业绩", "分红", "增持", "回购", "超预期", "增长", "盈利",
    "低估", "机会", "潜力", "价值"
]


def calculate_sentiment_with_keywords(
    text: str,
    ai_model=None,
    use_ai_fallback: bool = True
) -> Tuple[float, str]:
    """
    双重判定情感分析：
    1. 先检查关键词（强制规则，优先级最高）
    2. 如果没匹配到关键词，使用 AI 模型兜底
    
    Args:
        text: 待分析的文本（通常是 post_title）
        ai_model: AI 模型（Dianping pipeline），如果为 None 则跳过 AI 层
        use_ai_fallback: 是否在关键词未匹配时使用 AI 兜底
    
    Returns:
        Tuple[float, str]: (bullish_bearish_score, method)
        - bullish_bearish_score: -1.0（看空）到 +1.0（看多）的浮点数
        - method: "keyword_bearish" / "keyword_bullish" / "ai_positive" / "ai_negative" / "ai_neutral" / "fallback_neutral"
    """
    if not text or not isinstance(text, str):
        return 0.0, "fallback_neutral"
    
    text_lower = text.lower()
    
    # 第一层：关键词强制规则（优先级最高，覆盖 AI 模型）
    # 检查看空关键词
    for keyword in BEARISH_KEYWORDS:
        if keyword in text_lower:
            return -1.0, "keyword_bearish"
    
    # 检查看多关键词
    for keyword in BULLISH_KEYWORDS:
        if keyword in text_lower:
            return 1.0, "keyword_bullish"
    
    # 第二层：AI 兜底（只有当关键词都没匹配到，且模型可用时才调用）
    if use_ai_fallback and ai_model is not None:
        try:
            # Dianping 模型返回格式：
            # {"label": "positive (stars 4 and 5)" 或 "negative (stars 1, 2 and 3)", "score": 0.0~1.0}
            result = ai_model(text[:512])  # 限制长度避免超长文本
            
            # 处理批量返回（pipeline 可能返回列表）
            if isinstance(result, list) and len(result) > 0:
                result = result[0]
            
            label = result.get("label", "").lower()
            score = float(result.get("score", 0.5))
            
            # Dianping 模型的标签映射逻辑（参考用户原始代码）：
            # 'positive (stars 4 and 5)' -> 看多，返回 score (0~1)
            # 'negative (stars 1, 2 and 3)' -> 看空，返回 -score (-1~0)
            # 
            # 注意：Dianping 模型可能对金融文本有偏差，我们通过以下方式修正：
            # 1. 关键词规则优先级最高，会覆盖 AI 结果
            # 2. 保留 score 的强度信息，让低置信度的结果更接近 0
            
            if "positive" in label:
                # 正面情绪：返回 score (0~1)，保留原始强度
                return score, "ai_positive"
            elif "negative" in label:
                # 负面情绪：返回 -score (-1~0)，保留原始强度
                return -score, "ai_negative"
            else:
                # 未知标签，返回中性
                return 0.0, "ai_neutral"
        except Exception as e:
            # AI 模型调用失败，返回中性
            # 只在调试模式下打印详细错误（避免输出过多）
            import os
            if os.getenv("DEBUG_SENTIMENT", "").lower() == "true":
                import traceback
                print(f"[WARN] AI 模型调用失败: {e}")
                traceback.print_exc()
            return 0.0, "ai_fallback_neutral"
    
    # 如果既没匹配关键词，AI 也不可用，返回中性
    return 0.0, "fallback_neutral"


def load_stopwords(stopwords_dir: Optional[Path] = None) -> set:
    """
    加载所有停用词文件，合并成一个集合。
    
    Args:
        stopwords_dir: 停用词目录路径，默认为 spider/stopwords/
    
    Returns:
        set: 停用词集合
    """
    if stopwords_dir is None:
        base_dir = Path(__file__).resolve().parent
        stopwords_dir = base_dir / "stopwords"
    
    stopwords = set()
    
    if not stopwords_dir.exists():
        print(f"[WARN] 停用词目录不存在: {stopwords_dir}")
        return stopwords
    
    # 遍历目录下所有 .txt 文件
    for stopword_file in stopwords_dir.glob("*.txt"):
        try:
            with open(stopword_file, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word and not word.startswith("#"):  # 忽略空行和注释
                        stopwords.add(word)
            print(f"[INFO] 已加载停用词文件: {stopword_file.name} ({len(stopwords)} 个词)")
        except Exception as e:
            print(f"[WARN] 读取停用词文件失败 {stopword_file}: {e}")
    
    return stopwords
