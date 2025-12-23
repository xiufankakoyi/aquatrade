"""
使用 FinBERT 中文金融情感模型，遍历股吧抓取的所有评论，
为每条记录计算情绪得分并写回 CSV。

数据来源：
    spider/data 目录下的 *_posts.csv
写回字段：
    - sentiment_label  : 模型预测的情绪标签（Positive / Neutral / Negative）
    - sentiment_score  : 模型给出的置信度（0~1 的浮点数）

运行方式（建议在已创建好 spider/data/*.csv 之后执行）：
    cd d:/aquatrade
    python -m spider.calc_sentiment_finbert

【修复】GPU显存管理：
    - 使用单例模式避免重复加载模型
    - 添加显存清理逻辑（torch.cuda.empty_cache()）
    - 支持上下文管理器自动清理
"""

from pathlib import Path
from typing import List, Optional
import threading

import pandas as pd
from transformers import pipeline

# 尝试导入torch用于显存管理
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None


MAX_TEXT_LEN = 512  # FinBERT 输入的最大长度，超出的部分截断

# ==================== 单例模式：模型管理器 ====================
class SentimentModelManager:
    """
    单例模式管理情感分析模型，避免重复加载导致显存泄露
    """
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
    
    def get_classifier(self, force_reload: bool = False):
        """
        获取分类器实例（单例）
        
        Args:
            force_reload: 是否强制重新加载（会先清理显存）
        """
        with self._model_lock:
            if self._classifier is None or force_reload:
                if force_reload and self._classifier is not None:
                    # 清理旧模型
                    self._cleanup()
                
                print("正在加载情绪分析模型（首次运行会自动下载约 400MB 权重文件，请耐心等待）...")
                
                # 检测GPU可用性
                device = 0 if (TORCH_AVAILABLE and torch.cuda.is_available()) else -1
                if device >= 0:
                    print(f"[GPU] 检测到 CUDA，将使用 GPU 加速（设备: {torch.cuda.get_device_name(0)}）")
                else:
                    print("[CPU] 未检测到 CUDA，将使用 CPU")
                
                self._classifier = pipeline(
                    "sentiment-analysis",
                    model="yiyanghkust/finbert-tone-chinese",
                    device=device,
                )
                print("模型加载完成")
            
            return self._classifier
    
    def _cleanup(self):
        """清理模型和显存"""
        if self._classifier is not None:
            # 删除模型引用
            del self._classifier
            self._classifier = None
        
        # 清理GPU显存
        if TORCH_AVAILABLE and torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            print("[GPU] 显存已清理")
    
    def cleanup(self):
        """外部调用：清理模型和显存"""
        with self._model_lock:
            self._cleanup()
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口：自动清理"""
        # 注意：这里不自动清理，因为可能还要继续使用
        # 如果需要强制清理，可以调用 cleanup()
        pass


def chunk_list(items: List[str], batch_size: int) -> List[List[str]]:
    """将列表按 batch_size 分块，便于批量送入模型。"""
    return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"

    if not data_dir.exists():
        print(f"数据目录不存在: {data_dir}")
        return

    csv_files = sorted(data_dir.glob("*_posts.csv"))
    if not csv_files:
        print(f"目录中未找到 *_posts.csv: {data_dir}")
        return

    # 使用单例模式获取模型
    model_manager = SentimentModelManager()
    classifier = model_manager.get_classifier()
    print("开始遍历 CSV 文件...")

    for csv_path in csv_files:
        print(f"\n====== 处理文件: {csv_path.name} ======")
        try:
            df = pd.read_csv(csv_path, encoding="utf-8-sig")
        except Exception as e:  # noqa: BLE001
            print(f"读取失败，跳过 {csv_path}: {e}")
            continue

        if df is None or df.empty:
            print("  文件为空，跳过。")
            continue

        # 如果之前已经算过 sentiment_score，则只补算缺失行
        if "sentiment_score" not in df.columns:
            df["sentiment_score"] = pd.NA
        if "sentiment_label" not in df.columns:
            df["sentiment_label"] = pd.NA

        mask_need_calc = df["post_title"].notna() & (
            df["post_title"].astype(str).str.strip() != ""
        ) & df["sentiment_score"].isna()

        indices = df.index[mask_need_calc].tolist()
        if not indices:
            print("  所有记录均已有 sentiment_score，跳过计算。")
            continue

        print(f"  需计算情绪的记录数: {len(indices)}")

        texts = [str(df.at[i, "post_title"])[:MAX_TEXT_LEN] for i in indices]

        # 批量送入模型，避免一次性加载过多文本导致显存/内存压力
        batch_size = 32
        results_all = []
        for batch_idx, batch in enumerate(chunk_list(texts, batch_size)):
            # transformers 会自动在内部进行分词和推理
            batch_results = classifier(batch)
            results_all.extend(batch_results)
            
            # 每处理10个batch清理一次显存（避免碎片累积）
            if TORCH_AVAILABLE and torch.cuda.is_available() and (batch_idx + 1) % 10 == 0:
                torch.cuda.empty_cache()

        for row_idx, res in zip(indices, results_all):
            try:
                label = res.get("label")
                score = float(res.get("score", 0.0))
            except Exception:
                label = None
                score = None

            df.at[row_idx, "sentiment_label"] = label
            df.at[row_idx, "sentiment_score"] = score

        # 回写到原 CSV（保留原有字段顺序，新增字段会追加在末尾）
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"  已写回 sentiment_label / sentiment_score 至 {csv_path.name}")

    # 最终清理显存
    if TORCH_AVAILABLE and torch.cuda.is_available():
        torch.cuda.empty_cache()
        print("[GPU] 最终显存清理完成")
    
    print("\n全部文件处理完成。后续若重新运行，仅会为缺失 sentiment_score 的记录补算。")


if __name__ == "__main__":
    main()


