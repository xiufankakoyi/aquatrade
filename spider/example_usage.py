"""
情感分析模块使用示例
"""

from ensemble_sentiment_analyzer import (
    get_ensemble_analyzer,
    calculate_sentiment_ensemble
)
import pandas as pd
from typing import List, Tuple


def example_single_text():
    """示例1: 分析单个文本"""
    print("=" * 50)
    print("示例1: 分析单个文本")
    print("=" * 50)
    
    # 方法1: 使用便捷函数
    text = "主力资金大幅流入，市场情绪高涨。"
    score, method = calculate_sentiment_ensemble(text, use_keywords=False)
    print(f"文本: {text}")
    print(f"情感分数: {score:.4f} (范围: -1.0看跌 到 +1.0看涨)")
    print(f"分析方法: {method}")
    print()
    
    # 方法2: 使用分析器实例
    analyzer = get_ensemble_analyzer()
    if analyzer:
        score2, method2 = analyzer.analyze(text, use_keywords=True)
        print(f"使用关键词: 情感分数={score2:.4f}, 方法={method2}")
    print()


def example_batch_texts():
    """示例2: 批量分析多个文本（GPU加速）"""
    print("=" * 50)
    print("示例2: 批量分析多个文本（GPU加速）")
    print("=" * 50)
    
    texts = [
        "主力资金大幅流入，后市看涨。",
        "出货明显，建议减仓。",
        "横盘整理，观望为主。",
        "涨停了！主力在抢筹！",
        "破位下跌，风险加大。",
    ]
    
    analyzer = get_ensemble_analyzer()
    if analyzer:
        # 批量分析（GPU并行处理）
        results = analyzer.analyze_batch(
            texts, 
            batch_size=128,  # 批量大小，可根据GPU显存调整
            use_keywords=True  # 是否先检查关键词
        )
        
        print(f"共分析 {len(texts)} 条文本:\n")
        for i, (text, (score, method)) in enumerate(zip(texts, results), 1):
            sentiment = "看涨" if score > 0.3 else "看跌" if score < -0.3 else "中性"
            print(f"{i}. {text}")
            print(f"   分数: {score:+.4f} | 方法: {method} | 判断: {sentiment}")
            print()
    print()


def example_csv_file():
    """示例3: 处理CSV文件（实际应用场景）"""
    print("=" * 50)
    print("示例3: 处理CSV文件")
    print("=" * 50)
    
    # 假设你有一个包含评论/文本的CSV文件
    # CSV格式示例:
    # id,content,date
    # 1,主力资金大幅流入,2024-01-01
    # 2,出货明显建议减仓,2024-01-02
    # ...
    
    try:
        # 读取CSV文件
        df = pd.read_csv("your_data.csv")  # 替换为你的文件路径
        
        # 确保content列存在且为字符串类型
        if 'content' not in df.columns:
            print("❌ CSV文件中没有找到 'content' 列")
            return
        
        all_texts = df['content'].astype(str).tolist()
        print(f"📊 读取到 {len(all_texts)} 条数据")
        
        # 获取分析器
        analyzer = get_ensemble_analyzer()
        if analyzer:
            print("🚀 开始批量分析（GPU加速）...")
            
            # 一次性批量处理（GPU会并行处理，速度极快）
            scores_and_methods = analyzer.analyze_batch(
                all_texts, 
                batch_size=128,  # 可根据GPU显存调整：8GB显存用128，16GB可用256
                use_keywords=True
            )
            
            # 提取结果
            df['sentiment_score'] = [x[0] for x in scores_and_methods]
            df['sentiment_method'] = [x[1] for x in scores_and_methods]
            
            # 添加情感标签（可选）
            df['sentiment_label'] = df['sentiment_score'].apply(
                lambda x: '看涨' if x > 0.3 else ('看跌' if x < -0.3 else '中性')
            )
            
            # 保存结果
            output_file = "your_data_with_sentiment.csv"
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
            print(f"✅ 分析完成！结果已保存到: {output_file}")
            
            # 显示统计信息
            print("\n📈 情感分布统计:")
            print(df['sentiment_label'].value_counts())
            print(f"\n平均情感分数: {df['sentiment_score'].mean():.4f}")
            
    except FileNotFoundError:
        print("⚠️  文件不存在，请替换 'your_data.csv' 为实际文件路径")
    except Exception as e:
        print(f"❌ 处理出错: {e}")
    print()


def example_keywords():
    """示例4: 关键词规则的使用"""
    print("=" * 50)
    print("示例4: 关键词规则的使用")
    print("=" * 50)
    
    texts = [
        "主力在抢筹，后市看涨！",  # 包含看涨关键词"主力"、"抢筹"
        "出货明显，建议减仓。",    # 包含看跌关键词"出货"、"减仓"
        "今天市场表现不错。",      # 不包含关键词，使用模型分析
    ]
    
    analyzer = get_ensemble_analyzer()
    if analyzer:
        print("不使用关键词（纯模型分析）:")
        results_no_kw = analyzer.analyze_batch(texts, use_keywords=False)
        for text, (score, method) in zip(texts, results_no_kw):
            print(f"  {text} -> {score:+.4f} ({method})")
        
        print("\n使用关键词（先匹配关键词，再模型分析）:")
        results_with_kw = analyzer.analyze_batch(texts, use_keywords=True)
        for text, (score, method) in zip(texts, results_with_kw):
            print(f"  {text} -> {score:+.4f} ({method})")
    print()


def example_performance_tips():
    """示例5: 性能优化建议"""
    print("=" * 50)
    print("示例5: 性能优化建议")
    print("=" * 50)
    
    tips = """
    💡 性能优化建议:
    
    1. 批量大小 (batch_size):
       - 8GB GPU显存: 建议 batch_size=128
       - 16GB GPU显存: 建议 batch_size=256
       - 32GB GPU显存: 建议 batch_size=512
       - CPU模式: 建议 batch_size=32
    
    2. 关键词使用:
       - use_keywords=True: 先快速匹配关键词（CPU），再模型分析（GPU）
       - use_keywords=False: 纯模型分析（GPU），更准确但稍慢
       - 建议: 对于大量数据，使用关键词可以过滤掉一部分，减少GPU计算量
    
    3. 数据预处理:
       - 确保文本是字符串类型
       - 过滤掉空文本和None值
       - 文本长度建议控制在200字以内（代码会自动截断）
    
    4. 内存管理:
       - 处理超大数据集时，可以分批读取CSV
       - 使用 pandas 的 chunksize 参数分块读取
    """
    print(tips)


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("情感分析模块使用示例")
    print("=" * 50 + "\n")
    
    # 运行示例
    example_single_text()
    example_batch_texts()
    example_keywords()
    example_performance_tips()
    
    # 取消注释下面的行来运行CSV处理示例
    # example_csv_file()
    
    print("\n" + "=" * 50)
    print("示例运行完成！")
    print("=" * 50)





























