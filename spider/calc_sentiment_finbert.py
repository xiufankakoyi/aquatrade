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
"""

from pathlib import Path
from typing import List

import pandas as pd
from transformers import pipeline


MAX_TEXT_LEN = 512  # FinBERT 输入的最大长度，超出的部分截断


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

    print("正在加载情绪分析模型（首次运行会自动下载约 400MB 权重文件，请耐心等待）...")
    classifier = pipeline(
        "sentiment-analysis",
        model="yiyanghkust/finbert-tone-chinese",
    )
    print("模型加载完成，开始遍历 CSV 文件...")

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
        for batch in chunk_list(texts, batch_size):
            # transformers 会自动在内部进行分词和推理
            batch_results = classifier(batch)
            results_all.extend(batch_results)

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

    print("\n全部文件处理完成。后续若重新运行，仅会为缺失 sentiment_score 的记录补算。")


if __name__ == "__main__":
    main()


