# examples/daily_resonance_example.py
"""
每日共振复盘模块 - 使用示例

展示如何使用 Daily Resonance Replay 模块进行市场分析
"""
import os
import sys

# 添加项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_svc.daily_resonance_replay import DailyResonanceReplay
from data_svc.concept_data_loader import ConceptDataLoader
from data_svc.lance_manager import LanceDBManager


def example_1_basic_usage():
    """示例 1: 基本使用 - 单日复盘"""
    print("=" * 70)
    print("示例 1: 基本使用 - 单日复盘")
    print("=" * 70)
    
    # 创建分析器
    analyzer = DailyResonanceReplay()
    
    # 运行复盘（使用 2024年12月31日 作为示例）
    result = analyzer.run_daily_replay('20241231')
    
    if result['success']:
        print("\n✅ 复盘成功！")
        print(f"主线概念: {result['stats']['main_themes']}")
    else:
        print(f"\n❌ 复盘失败: {result['error']}")


def example_2_batch_replay():
    """示例 2: 批量复盘 - 分析一周的数据"""
    print("\n" + "=" * 70)
    print("示例 2: 批量复盘 - 分析多个交易日")
    print("=" * 70)
    
    # 交易日列表（示例）
    trade_dates = [
        '20241227',
        '20241230',
        '20241231',
    ]
    
    analyzer = DailyResonanceReplay()
    
    results = []
    for date in trade_dates:
        print(f"\n处理 {date}...")
        result = analyzer.run_daily_replay(date)
        
        if result['success']:
            results.append({
                'date': date,
                'themes': result['stats']['main_themes'][:3],  # 前3个主线
                'total': result['stats']['total_limits']
            })
    
    # 汇总结果
    print("\n📊 批量复盘汇总:")
    for r in results:
        print(f"  {r['date']}: {r['total']} 只涨停, 主线: {r['themes']}")


def example_3_query_history():
    """示例 3: 查询历史数据"""
    print("\n" + "=" * 70)
    print("示例 3: 查询历史复盘数据")
    print("=" * 70)
    
    # 打开历史表
    mgr = LanceDBManager(table_name="daily_limit_history")
    
    # 查询指定日期的数据
    df = mgr.load_to_polars(
        start_date='20241231',
        end_date='20241231',
        columns=['stock_name', 'concept_resonance', 'resonance_rank', 
                'inst_net_buy', 'strength_score']
    ).to_pandas()
    
    if not df.empty:
        print(f"\n找到 {len(df)} 条记录")
        
        # 按共振排名排序
        df_sorted = df.sort_values('resonance_rank')
        
        print("\n🎯 主线龙头股票 (共振排名前10):")
        print(df_sorted.head(10).to_string(index=False))
    else:
        print("\n未找到数据")


def example_4_concept_analysis():
    """示例 4: 概念分析 - 查看特定概念的股票"""
    print("\n" + "=" * 70)
    print("示例 4: 概念分析 - 筛选特定主线")
    print("=" * 70)
    
    mgr = LanceDBManager(table_name="daily_limit_history")
    
    # 查询数据
    df = mgr.load_to_polars(
        start_date='20241231',
        end_date='20241231'
    ).to_pandas()
    
    if not df.empty:
        # 筛选特定概念（示例：假设"华为"是主线）
        # 实际使用时，先运行复盘查看有哪些主线
        
        # 统计各主线的股票数量
        theme_counts = df['concept_resonance'].value_counts()
        
        print("\n📊 主线概念分布:")
        for theme, count in theme_counts.head(10).items():
            print(f"  - {theme}: {count} 只")
        
        # 查看最强主线的详细股票
        if len(theme_counts) > 0:
            top_theme = theme_counts.index[0]
            df_theme = df[df['concept_resonance'] == top_theme]
            
            print(f"\n🔥 最强主线 [{top_theme}] 的股票:")
            print(df_theme[['stock_name', 'limit_times', 'inst_net_buy', 'strength_score']]
                  .sort_values('strength_score', ascending=False)
                  .head(5)
                  .to_string(index=False))


def example_5_update_concepts():
    """示例 5: 更新概念库"""
    print("\n" + "=" * 70)
    print("示例 5: 更新概念知识库")
    print("=" * 70)
    
    # 创建概念加载器
    loader = ConceptDataLoader()
    
    # 更新概念表（限制前50个概念，用于测试）
    # 正式使用时，去掉 limit 参数以获取全部概念
    loader.update_concepts_table(limit=50, force_rebuild=False)
    
    print("\n✓ 概念库更新完成")


def main():
    """运行所有示例"""
    print("🚀 每日共振复盘模块 - 使用示例集")
    print("=" * 70)
    
    try:
        # 示例 1: 基本使用
        example_1_basic_usage()
        
        # 示例 2: 批量复盘（可选，注释掉以节省时间）
        # example_2_batch_replay()
        
        # 示例 3: 查询历史
        example_3_query_history()
        
        # 示例 4: 概念分析
        example_4_concept_analysis()
        
        # 示例 5: 更新概念库（可选）
        # example_5_update_concepts()
        
        print("\n" + "=" * 70)
        print("✅ 所有示例运行完成！")
        print("=" * 70)
    
    except Exception as e:
        print(f"\n❌ 示例运行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
