"""
批量清洗情感数据脚本
- 重新计算所有帖子的 bullish_bearish 分数（使用双重判定逻辑）
- 更新 CSV 文件和 Parquet 文件
- 支持增量更新（只处理缺失或需要重新计算的记录）

运行方式：
    cd d:/aquatrade
    python -m spider.clean_sentiment_data
"""

import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from spider.sentiment_analyzer import calculate_sentiment_with_keywords
from spider.ensemble_sentiment_analyzer import calculate_sentiment_ensemble

try:
    from transformers import pipeline
    from spider.sentiment_analyzer import DIANPING_MODEL_NAME
    AI_MODEL_AVAILABLE = True
except ImportError:
    print("[WARN] transformers 库未安装，将只使用关键词规则，跳过 AI 模型")
    AI_MODEL_AVAILABLE = False
    DIANPING_MODEL_NAME = None
except Exception:
    DIANPING_MODEL_NAME = "dianping/sentiment-analysis-chinese"  # 默认值


def clean_csv_file(
    csv_path: Path,
    ai_model=None,
    force_recalculate: bool = False,
    dry_run: bool = False,
    use_ensemble: bool = False
) -> dict:
    """
    清洗单个 CSV 文件的情感数据
    
    Args:
        csv_path: CSV 文件路径
        ai_model: AI 模型（可选）
        force_recalculate: 是否强制重新计算所有记录
        dry_run: 是否为试运行（不实际写回文件）
    
    Returns:
        dict: 统计信息
    """
    print(f"\n====== 处理文件: {csv_path.name} ======")
    
    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig")
    except Exception as e:
        print(f"  读取失败，跳过: {e}")
        return {"error": str(e)}
    
    if df is None or df.empty:
        print("  文件为空，跳过")
        return {"skipped": True}
    
    # 确保必要字段存在
    if "post_title" not in df.columns:
        print("  缺少 post_title 字段，跳过")
        return {"skipped": True, "reason": "missing_post_title"}
    
    # 初始化或检查 bullish_bearish 字段（确保是 float 类型）
    if "bullish_bearish" not in df.columns:
        df["bullish_bearish"] = pd.NA
        df["sentiment_method"] = pd.NA
    else:
        # 确保列类型是 float，避免 FutureWarning
        df["bullish_bearish"] = pd.to_numeric(df["bullish_bearish"], errors="coerce").astype("float64")
    
    # 确保 sentiment_method 列存在
    if "sentiment_method" not in df.columns:
        df["sentiment_method"] = pd.NA
    
    # 确定需要计算的记录
    if force_recalculate:
        mask_need_calc = df["post_title"].notna() & (
            df["post_title"].astype(str).str.strip() != ""
        )
    else:
        # 只计算缺失或为 0 的记录
        mask_need_calc = (
            df["post_title"].notna() &
            (df["post_title"].astype(str).str.strip() != "") &
            (
                df["bullish_bearish"].isna() |
                (pd.to_numeric(df["bullish_bearish"], errors="coerce").fillna(0) == 0)
            )
        )
    
    indices = df.index[mask_need_calc].tolist()
    
    if not indices:
        print("  所有记录均已有有效的 bullish_bearish 分数，跳过计算")
        return {
            "total": len(df),
            "processed": 0,
            "skipped": True
        }
    
    print(f"  需计算情感分数的记录数: {len(indices)} / {len(df)}")
    
    # 统计信息
    stats = {
        "total": len(df),
        "processed": 0,
        "keyword_bearish": 0,
        "keyword_bullish": 0,
        "ai_positive": 0,
        "ai_negative": 0,
        "ai_neutral": 0,
        "fallback_neutral": 0,
        "errors": 0
    }
    
    # 【性能优化】先收集所有数据，再一次性批量处理（避免"小批次喂食"）
    # 关键：先攒够足够的数据（比如5000条），让GPU能连续满载工作
    if use_ensemble:
        # 使用集成模型的批量接口
        from spider.ensemble_sentiment_analyzer import get_ensemble_analyzer
        analyzer = get_ensemble_analyzer()
        
        if analyzer:
            # 【关键优化】先收集所有需要处理的文本和索引
            all_texts = []
            all_df_indices = []
            
            print(f"  收集需要处理的文本...")
            for idx in indices:
                title = str(df.at[idx, "post_title"]).strip()
                if title:
                    all_texts.append(title)
                    all_df_indices.append(idx)
            
            if not all_texts:
                print("  没有需要处理的文本")
            else:
                print(f"  共收集到 {len(all_texts)} 条文本，开始批量分析（GPU将连续满载工作）...")
                
                try:
                    # 【关键】一次性批量处理所有数据，让 analyze_batch 内部自动切分
                    # analyze_batch 内部会按 128 切分，GPU 可以连续工作，流水线效应最大化
                    all_results = analyzer.analyze_batch(all_texts, use_keywords=False)
                    
                    # 批量更新 DataFrame 和统计
                    for text_idx, (score, method) in enumerate(all_results):
                        df_idx = all_df_indices[text_idx]
                        df.at[df_idx, "bullish_bearish"] = float(score)
                        df.at[df_idx, "sentiment_method"] = str(method)
                        
                        stats["processed"] += 1
                        if "keyword_bearish" in method:
                            stats["keyword_bearish"] += 1
                        elif "keyword_bullish" in method:
                            stats["keyword_bullish"] += 1
                        elif "ensemble_weighted" in method:
                            if score > 0.1:
                                stats["ai_positive"] += 1
                            elif score < -0.1:
                                stats["ai_negative"] += 1
                            else:
                                stats["ai_neutral"] += 1
                        else:
                            stats["fallback_neutral"] += 1
                    
                    print(f"  ✅ 批量处理完成，共处理 {stats['processed']} 条记录")
                
                except Exception as e:
                    print(f"  ❌ 批量处理失败，回退到逐条处理: {e}")
                    import traceback
                    traceback.print_exc()
                    # 回退到逐条处理
                    for idx in indices:
                        try:
                            title = str(df.at[idx, "post_title"]).strip()
                            if not title:
                                continue
                            score, method = analyzer.analyze(title, use_keywords=False)
                            df.at[idx, "bullish_bearish"] = float(score)
                            df.at[idx, "sentiment_method"] = str(method)
                            stats["processed"] += 1
                        except Exception as e2:
                            stats["errors"] += 1
                            continue
        else:
            print("  ⚠️  集成分析器不可用，回退到逐条处理")
            use_ensemble = False
    
    # 逐条处理（回退方案或非集成模式）
    if not use_ensemble:
        for idx in indices:
            try:
                title = str(df.at[idx, "post_title"]).strip()
                if not title:
                    continue
                
                # 使用单个模型（兼容旧逻辑）
                use_ai = (ai_model is not None)
                score, method = calculate_sentiment_with_keywords(
                    title,
                    ai_model=ai_model,
                    use_ai_fallback=use_ai
                )
                
                # 更新 DataFrame（确保类型正确）
                df.at[idx, "bullish_bearish"] = float(score)
                df.at[idx, "sentiment_method"] = str(method)
                
                # 更新统计
                stats["processed"] += 1
                if "keyword_bearish" in method:
                    stats["keyword_bearish"] += 1
                elif "keyword_bullish" in method:
                    stats["keyword_bullish"] += 1
                elif "ai_positive" in method or (score > 0.1 and "ai" in method):
                    stats["ai_positive"] += 1
                elif "ai_negative" in method or (score < -0.1 and "ai" in method):
                    stats["ai_negative"] += 1
                elif "ai_neutral" in method or ("ai" in method and -0.1 <= score <= 0.1):
                    stats["ai_neutral"] += 1
                else:
                    stats["fallback_neutral"] += 1
                
                # 每处理 100 条打印一次进度
                if stats["processed"] % 100 == 0:
                    print(f"    已处理 {stats['processed']} / {len(indices)} 条记录...")
            
            except Exception as e:
                print(f"    处理第 {idx} 条记录时出错: {e}")
                stats["errors"] += 1
                continue
    
    # 写回文件（如果不是试运行）
    if not dry_run:
        try:
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            print(f"  ✅ 已写回 {csv_path.name}")
        except Exception as e:
            print(f"  ❌ 写回失败: {e}")
            stats["write_error"] = str(e)
    else:
        print(f"  [DRY RUN] 未实际写回文件")
    
    # 打印统计信息
    print(f"  统计:")
    print(f"    - 关键词看空: {stats['keyword_bearish']}")
    print(f"    - 关键词看多: {stats['keyword_bullish']}")
    print(f"    - AI 看多: {stats['ai_positive']}")
    print(f"    - AI 看空: {stats['ai_negative']}")
    print(f"    - AI 中性: {stats['ai_neutral']}")
    print(f"    - 回退中性: {stats['fallback_neutral']}")
    print(f"    - 错误: {stats['errors']}")
    
    return stats


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="批量清洗情感数据")
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新计算所有记录（即使已有分数）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="试运行模式（不实际写回文件）"
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="不使用 AI 模型，仅使用关键词规则"
    )
    parser.add_argument(
        "--use-ensemble",
        action="store_true",
        help="使用集成模型（5个模型加权平均，准确率93.3%，推荐）"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="只处理指定的单个文件（相对于 spider/data/）"
    )
    
    args = parser.parse_args()
    
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"
    
    if not data_dir.exists():
        print(f"❌ 数据目录不存在: {data_dir}")
        return
    
    # 加载 AI 模型（默认使用，关键词优先）
    # 逻辑：先检查关键词，如果匹配就返回；如果没有关键词，才使用 AI 模型
    ai_model = None
    print(f"\n{'='*60}")
    print(f"AI 模型配置检查:")
    print(f"  - args.no_ai: {args.no_ai}")
    print(f"  - AI_MODEL_AVAILABLE: {AI_MODEL_AVAILABLE}")
    print(f"  - DIANPING_MODEL_NAME: {DIANPING_MODEL_NAME}")
    print(f"{'='*60}\n")
    
    if not args.no_ai and AI_MODEL_AVAILABLE:
        print(f"正在加载 Dianping 情感分析模型: {DIANPING_MODEL_NAME}")
        print("（首次运行会自动下载模型权重文件，请耐心等待）...")
        try:
            ai_model = pipeline(
                "sentiment-analysis",
                model=DIANPING_MODEL_NAME,
                device=0,
            )   
            print("✅ 模型加载完成")
            
            # 测试模型是否正常工作
            test_text = "测试文本：今天股票涨停了！"
            test_result = ai_model(test_text)
            print(f"✅ 模型测试成功")
            print(f"   测试文本: {test_text}")
            print(f"   返回结果: {test_result}")
            print(f"   返回类型: {type(test_result)}")
            if isinstance(test_result, list) and len(test_result) > 0:
                print(f"   第一个结果: {test_result[0]}")
        except Exception as e:
            import traceback
            print(f"❌ 模型加载失败，将只使用关键词规则")
            print(f"   错误类型: {type(e).__name__}")
            print(f"   错误详情: {e}")
            print(f"   完整堆栈:")
            traceback.print_exc()
            ai_model = None
    else:
        if args.no_ai:
            print("ℹ️  跳过 AI 模型（--no-ai 参数），仅使用关键词规则")
        else:
            print("ℹ️  跳过 AI 模型（transformers 库不可用），仅使用关键词规则")
    
    print(f"\n最终状态: ai_model = {ai_model is not None}")
    print(f"{'='*60}\n")
    
    # 确定要处理的文件列表
    if args.file:
        csv_files = [data_dir / args.file]
        if not csv_files[0].exists():
            print(f"❌ 文件不存在: {csv_files[0]}")
            return
    else:
        csv_files = sorted(data_dir.glob("*_posts.csv"))
    
    if not csv_files:
        print(f"❌ 目录中未找到 *_posts.csv: {data_dir}")
        return
    
    print(f"\n找到 {len(csv_files)} 个 CSV 文件")
    if args.dry_run:
        print("⚠️  试运行模式：不会实际修改文件")
    if args.force:
        print("⚠️  强制模式：将重新计算所有记录")
    
    # 汇总统计
    total_stats = {
        "files_processed": 0,
        "files_skipped": 0,
        "total_records": 0,
        "total_processed": 0,
        "keyword_bearish": 0,
        "keyword_bullish": 0,
        "ai_positive": 0,
        "ai_negative": 0,
        "ai_neutral": 0,
        "fallback_neutral": 0,
        "errors": 0
    }
    
    # 【性能优化】跨文件批量收集（单个CSV数据量少，需要跨文件收集才能充分利用GPU）
    if args.use_ensemble and not args.file:
        print(f"\n[跨文件优化] 显存只用3.1GB/8GB，将跨文件收集数据以最大化GPU利用率...")
        
        from spider.ensemble_sentiment_analyzer import get_ensemble_analyzer
        analyzer = get_ensemble_analyzer()
        
        if analyzer:
            # 跨文件数据收集结构：[(csv_path, df, idx, title), ...]
            cross_file_data = []
            target_batch_size = 5000  # 目标批量大小，攒够5000条再处理
            
            print(f"  第一阶段：扫描所有文件，收集需要处理的文本...")
            for csv_path in csv_files:
                try:
                    df = pd.read_csv(csv_path, encoding="utf-8-sig")
                except Exception as e:
                    print(f"  跳过 {csv_path.name}: 读取失败 - {e}")
                    total_stats["errors"] += 1
                    continue
                
                if df is None or df.empty or "post_title" not in df.columns:
                    total_stats["files_skipped"] += 1
                    continue
                
                # 确保必要字段存在
                if "bullish_bearish" not in df.columns:
                    df["bullish_bearish"] = pd.NA
                if "sentiment_method" not in df.columns:
                    df["sentiment_method"] = pd.NA
                
                # 确定需要计算的记录
                if args.force:
                    mask_need_calc = df["post_title"].notna() & (
                        df["post_title"].astype(str).str.strip() != ""
                    )
                else:
                    mask_need_calc = (
                        df["post_title"].notna() &
                        (df["post_title"].astype(str).str.strip() != "") &
                        (
                            df["bullish_bearish"].isna() |
                            (pd.to_numeric(df["bullish_bearish"], errors="coerce").fillna(0) == 0)
                        )
                    )
                
                indices = df.index[mask_need_calc].tolist()
                
                if not indices:
                    total_stats["files_skipped"] += 1
                    continue
                
                # 收集需要处理的数据
                for idx in indices:
                    title = str(df.at[idx, "post_title"]).strip()
                    if title:
                        cross_file_data.append((csv_path, df, idx, title))
                
                total_stats["total_records"] += len(df)
            
            print(f"  共收集到 {len(cross_file_data)} 条需要处理的文本（来自 {len(csv_files)} 个文件）")
            
            if cross_file_data:
                # 批量处理：按目标批量大小切分
                all_texts = [item[3] for item in cross_file_data]  # 提取所有文本
                
                print(f"  开始批量分析（批量大小: {target_batch_size}，GPU将连续满载工作）...")
                
                try:
                    # 【关键】一次性批量处理所有数据
                    all_results = analyzer.analyze_batch(all_texts, use_keywords=False)
                    
                    # 批量更新所有文件的DataFrame
                    processed_count = 0
                    for data_idx, (score, method) in enumerate(all_results):
                        csv_path, df, idx, title = cross_file_data[data_idx]
                        
                        df.at[idx, "bullish_bearish"] = float(score)
                        df.at[idx, "sentiment_method"] = str(method)
                        
                        processed_count += 1
                        total_stats["total_processed"] += 1
                        
                        # 统计
                        if "keyword_bearish" in method:
                            total_stats["keyword_bearish"] += 1
                        elif "keyword_bullish" in method:
                            total_stats["keyword_bullish"] += 1
                        elif "ensemble_weighted" in method:
                            if score > 0.1:
                                total_stats["ai_positive"] += 1
                            elif score < -0.1:
                                total_stats["ai_negative"] += 1
                            else:
                                total_stats["ai_neutral"] += 1
                        else:
                            total_stats["fallback_neutral"] += 1
                        
                        # 每处理1000条打印进度
                        if processed_count % 1000 == 0:
                            print(f"    已处理 {processed_count} / {len(cross_file_data)} 条记录...")
                    
                    print(f"  ✅ 批量分析完成，共处理 {processed_count} 条记录")
                    
                    # 批量写回所有文件
                    print(f"  第二阶段：写回所有文件...")
                    file_dfs = {}  # {csv_path: df} 去重，避免重复写同一个文件
                    for csv_path, df, idx, title in cross_file_data:
                        file_dfs[csv_path] = df
                    
                    for csv_path, df in file_dfs.items():
                        if not args.dry_run:
                            try:
                                df.to_csv(csv_path, index=False, encoding="utf-8-sig")
                                total_stats["files_processed"] += 1
                            except Exception as e:
                                print(f"  ❌ 写回文件失败 {csv_path.name}: {e}")
                                total_stats["errors"] += 1
                        else:
                            total_stats["files_processed"] += 1
                    
                    print(f"  ✅ 已写回 {len(file_dfs)} 个文件")
                
                except Exception as e:
                    print(f"  ❌ 跨文件批量处理失败: {e}")
                    import traceback
                    traceback.print_exc()
                    total_stats["errors"] += len(cross_file_data)
                    # 回退到单文件处理
                    print(f"  回退到单文件处理模式...")
                    for csv_path in csv_files:
                        stats = clean_csv_file(
                            csv_path,
                            ai_model=ai_model,
                            force_recalculate=args.force,
                            dry_run=args.dry_run,
                            use_ensemble=args.use_ensemble
                        )
                        if stats.get("skipped"):
                            total_stats["files_skipped"] += 1
                        elif "error" in stats:
                            total_stats["errors"] += 1
                        else:
                            total_stats["files_processed"] += 1
                            total_stats["total_records"] += stats.get("total", 0)
                            total_stats["total_processed"] += stats.get("processed", 0)
                            total_stats["keyword_bearish"] += stats.get("keyword_bearish", 0)
                            total_stats["keyword_bullish"] += stats.get("keyword_bullish", 0)
                            total_stats["ai_positive"] += stats.get("ai_positive", 0)
                            total_stats["ai_negative"] += stats.get("ai_negative", 0)
                            total_stats["ai_neutral"] += stats.get("ai_neutral", 0)
                            total_stats["fallback_neutral"] += stats.get("fallback_neutral", 0)
                            total_stats["errors"] += stats.get("errors", 0)
            else:
                print("  没有需要处理的数据")
        else:
            print("  ⚠️  集成分析器不可用，回退到单文件处理")
            # 回退到单文件处理
            for csv_path in csv_files:
                stats = clean_csv_file(
                    csv_path,
                    ai_model=ai_model,
                    force_recalculate=args.force,
                    dry_run=args.dry_run,
                    use_ensemble=args.use_ensemble
                )
                if stats.get("skipped"):
                    total_stats["files_skipped"] += 1
                elif "error" in stats:
                    total_stats["errors"] += 1
                else:
                    total_stats["files_processed"] += 1
                    total_stats["total_records"] += stats.get("total", 0)
                    total_stats["total_processed"] += stats.get("processed", 0)
                    total_stats["keyword_bearish"] += stats.get("keyword_bearish", 0)
                    total_stats["keyword_bullish"] += stats.get("keyword_bullish", 0)
                    total_stats["ai_positive"] += stats.get("ai_positive", 0)
                    total_stats["ai_negative"] += stats.get("ai_negative", 0)
                    total_stats["ai_neutral"] += stats.get("ai_neutral", 0)
                    total_stats["fallback_neutral"] += stats.get("fallback_neutral", 0)
                    total_stats["errors"] += stats.get("errors", 0)
    else:
        # 单文件处理模式（指定单个文件或非集成模式）
        for csv_path in csv_files:
            stats = clean_csv_file(
                csv_path,
                ai_model=ai_model,
                force_recalculate=args.force,
                dry_run=args.dry_run,
                use_ensemble=args.use_ensemble
            )
            
            if stats.get("skipped"):
                total_stats["files_skipped"] += 1
                continue
            
            if "error" in stats:
                total_stats["errors"] += 1
                continue
            
            total_stats["files_processed"] += 1
            total_stats["total_records"] += stats.get("total", 0)
            total_stats["total_processed"] += stats.get("processed", 0)
            total_stats["keyword_bearish"] += stats.get("keyword_bearish", 0)
            total_stats["keyword_bullish"] += stats.get("keyword_bullish", 0)
            total_stats["ai_positive"] += stats.get("ai_positive", 0)
            total_stats["ai_negative"] += stats.get("ai_negative", 0)
            total_stats["ai_neutral"] += stats.get("ai_neutral", 0)
            total_stats["fallback_neutral"] += stats.get("fallback_neutral", 0)
            total_stats["errors"] += stats.get("errors", 0)
    
    # 打印汇总统计
    print("\n" + "=" * 60)
    print("汇总统计:")
    print(f"  处理文件数: {total_stats['files_processed']}")
    print(f"  跳过文件数: {total_stats['files_skipped']}")
    print(f"  总记录数: {total_stats['total_records']}")
    print(f"  已处理记录数: {total_stats['total_processed']}")
    print(f"\n情感分布:")
    print(f"  关键词看空: {total_stats['keyword_bearish']}")
    print(f"  关键词看多: {total_stats['keyword_bullish']}")
    print(f"  AI 看多: {total_stats['ai_positive']}")
    print(f"  AI 看空: {total_stats['ai_negative']}")
    print(f"  AI 中性: {total_stats['ai_neutral']}")
    print(f"  回退中性: {total_stats['fallback_neutral']}")
    print(f"  错误数: {total_stats['errors']}")
    print("=" * 60)
    
    if not args.dry_run:
        print("\n✅ 清洗完成！建议重新生成 Parquet 文件以同步更新。")
        print("   运行: python scripts/build_guba_posts_parquet.py")


if __name__ == "__main__":
    main()

