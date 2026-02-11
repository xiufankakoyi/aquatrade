# test_resonance_replay.py
"""
每日共振复盘模块测试脚本

测试流程：
1. 初始化概念库（如果不存在）
2. 运行指定日期的复盘分析
3. 验证数据质量
"""
import os
import sys
from datetime import datetime

# 添加项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.logger import get_logger
from data_svc.concept_data_loader import ConceptDataLoader
from data_svc.daily_resonance_replay import DailyResonanceReplay
from data_svc.lance_manager import LanceDBManager

logger = get_logger(__name__)


def check_concept_table() -> bool:
    """检查概念表是否存在"""
    try:
        mgr = LanceDBManager(table_name="stock_concepts")
        info = mgr.get_table_info()
        
        if info.get('exists'):
            logger.info(f"✓ 概念表已存在，共 {info.get('rows', 0)} 条记录")
            return True
        else:
            logger.warning("⚠️ 概念表不存在")
            return False
    except Exception as e:
        logger.warning(f"检查概念表失败: {e}")
        return False


def initialize_concept_table(limit: int = 50):
    """
    初始化概念表（首次运行）
    
    Args:
        limit: 限制处理的概念数量（测试用，None 表示全部）
    """
    logger.info("=" * 70)
    logger.info("🧠 初始化概念知识库...")
    logger.info("=" * 70)
    
    try:
        loader = ConceptDataLoader()
        loader.update_concepts_table(limit=limit, force_rebuild=False)
        logger.info("✓ 概念表初始化完成")
        return True
    except Exception as e:
        logger.error(f"❌ 概念表初始化失败: {e}")
        return False


def run_replay_test(trade_date: str):
    """
    运行复盘测试
    
    Args:
        trade_date: 交易日期 (格式: YYYYMMDD)
    """
    logger.info("=" * 70)
    logger.info(f"🚀 测试每日复盘: {trade_date}")
    logger.info("=" * 70)
    
    try:
        # 创建分析器
        analyzer = DailyResonanceReplay()
        
        # 执行复盘
        result = analyzer.run_daily_replay(trade_date)
        
        if result['success']:
            logger.info("\n✅ 测试成功！")
            
            # 显示详细统计
            stats = result['stats']
            logger.info("\n📊 复盘统计:")
            logger.info(f"  - 交易日期: {stats['trade_date']}")
            logger.info(f"  - 涨停总数: {stats['total_limits']} 只")
            logger.info(f"  - 主线概念: {stats['main_themes']}")
            logger.info(f"  - 机构参与: {stats['inst_coverage']} 只")
            logger.info(f"  - 平均强度: {stats['avg_strength']:.4f}")
            logger.info(f"  - 执行耗时: {result['elapsed']:.2f} 秒")
            
            return True
        else:
            logger.error(f"\n❌ 测试失败: {result.get('error', '未知错误')}")
            return False
    
    except Exception as e:
        logger.error(f"❌ 测试异常: {e}", exc_info=True)
        return False


def verify_data_quality(trade_date: str):
    """
    验证数据质量
    
    Args:
        trade_date: 交易日期
    """
    logger.info("\n" + "=" * 70)
    logger.info("🔍 验证数据质量...")
    logger.info("=" * 70)
    
    try:
        # 查询当日数据
        mgr = LanceDBManager(table_name="daily_limit_history")
        
        df = mgr.load_to_polars(
            start_date=trade_date,
            end_date=trade_date
        ).to_pandas()
        
        if df.empty:
            logger.warning("⚠️ 未找到数据")
            return False
        
        logger.info(f"\n✓ 找到 {len(df)} 条记录")
        
        # 数据质量检查
        logger.info("\n📋 数据质量报告:")
        
        # 1. 概念覆盖率
        has_concepts = df['concept_tags'].notna().sum()
        concept_coverage = has_concepts / len(df) * 100
        logger.info(f"  - 概念覆盖率: {concept_coverage:.1f}% ({has_concepts}/{len(df)})")
        
        # 2. 主线归属
        main_theme_count = df[df['concept_resonance'] != '杂毛/独立逻辑'].shape[0]
        main_theme_ratio = main_theme_count / len(df) * 100
        logger.info(f"  - 主线归属率: {main_theme_ratio:.1f}% ({main_theme_count}/{len(df)})")
        
        # 3. 机构参与
        inst_count = df[df['inst_net_buy'] > 0].shape[0]
        inst_ratio = inst_count / len(df) * 100
        logger.info(f"  - 机构参与率: {inst_ratio:.1f}% ({inst_count}/{len(df)})")
        
        # 4. 强度分布
        logger.info(f"  - 强度得分: 最小={df['strength_score'].min():.4f}, "
                   f"平均={df['strength_score'].mean():.4f}, "
                   f"最大={df['strength_score'].max():.4f}")
        
        # 5. 主线分布
        logger.info("\n🎯 主线概念分布:")
        theme_dist = df['concept_resonance'].value_counts().head(10)
        for theme, count in theme_dist.items():
            ratio = count / len(df) * 100
            logger.info(f"  - {theme}: {count} 只 ({ratio:.1f}%)")
        
        # 6. 示例数据
        logger.info("\n📝 示例数据 (前3条):")
        sample_cols = ['stock_name', 'concept_resonance', 'resonance_rank', 
                      'inst_net_buy', 'strength_score']
        print(df[sample_cols].head(3).to_string(index=False))
        
        return True
    
    except Exception as e:
        logger.error(f"❌ 数据验证失败: {e}", exc_info=True)
        return False


def main():
    """主测试流程"""
    import argparse
    
    parser = argparse.ArgumentParser(description='每日共振复盘测试')
    parser.add_argument('--date', type=str, default='20241231',
                       help='测试日期 (格式: YYYYMMDD, 默认: 20241231)')
    parser.add_argument('--init-concepts', action='store_true',
                       help='初始化概念表（首次运行）')
    parser.add_argument('--concept-limit', type=int, default=50,
                       help='概念表初始化时的限制数量（测试用）')
    parser.add_argument('--skip-verify', action='store_true',
                       help='跳过数据验证')
    
    args = parser.parse_args()
    
    logger.info("=" * 70)
    logger.info("📊 每日共振复盘模块 - 测试脚本")
    logger.info("=" * 70)
    
    # Step 1: 检查概念表
    concept_exists = check_concept_table()
    
    if not concept_exists or args.init_concepts:
        logger.info("\n需要初始化概念表...")
        if not initialize_concept_table(limit=args.concept_limit):
            logger.error("概念表初始化失败，终止测试")
            sys.exit(1)
    
    # Step 2: 运行复盘测试
    if not run_replay_test(args.date):
        logger.error("复盘测试失败")
        sys.exit(1)
    
    # Step 3: 验证数据质量
    if not args.skip_verify:
        if not verify_data_quality(args.date):
            logger.warning("数据验证失败（非致命错误）")
    
    logger.info("\n" + "=" * 70)
    logger.info("✅ 所有测试完成！")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
