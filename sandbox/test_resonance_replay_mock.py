# test_resonance_replay_mock.py
"""
每日共振复盘模块 - Mock 测试脚本

用于在 Tushare API 配额耗尽时，测试核心逻辑（概念共振计算 + 入库）
"""
import os
import sys
import pandas as pd
from unittest.mock import MagicMock, patch

# 添加项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.logger import get_logger
from data_svc.daily_resonance_replay import DailyResonanceReplay
from data_svc.lance_manager import LanceDBManager

logger = get_logger(__name__)

def run_mock_test():
    """运行 Mock 测试"""
    logger.info("=" * 70)
    logger.info("🚀 运行 Mock 复盘测试 (不消耗 API 配额)")
    logger.info("=" * 70)
    
    # 1. 构造 Mock 数据
    # 模拟涨停股票列表
    mock_limits = pd.DataFrame([
        {'ts_code': '000001.SZ', 'name': '平安银行', 'limit_times': 1, 'fd_amount': 10000, 'circ_mv': 200000},  # 银行
        {'ts_code': '600519.SH', 'name': '贵州茅台', 'limit_times': 2, 'fd_amount': 50000, 'circ_mv': 2000000}, # 白酒
        {'ts_code': '000858.SZ', 'name': '五粮液',   'limit_times': 1, 'fd_amount': 20000, 'circ_mv': 500000},  # 白酒
        {'ts_code': '600036.SH', 'name': '招商银行', 'limit_times': 1, 'fd_amount': 15000, 'circ_mv': 800000},  # 银行
        {'ts_code': '999999.SZ', 'name': '虚拟牛股', 'limit_times': 5, 'fd_amount': 5000,  'circ_mv': 10000},   # 概念A
    ])
    
    # 模拟机构资金
    mock_smart_money = {
        '000001.SZ': 5000.0,
        '600519.SH': 10000.0
    }
    
    # 模拟概念数据 (Stock -> Concepts)
    # 我们需要在 LanceDB 中有一些数据，或者 Mock enrich_with_concepts 方法
    # 这里我们选择 Mock enrich_with_concepts 方法，这样就不依赖本地数据库了
    
    logger.info("构建 Mock 环境...")
    
    analyzer = DailyResonanceReplay(tushare_token="mock_token")
    
    # Mock Step 1: get_raw_market_data
    analyzer.get_raw_market_data = MagicMock(return_value=(mock_limits, mock_smart_money))
    
    # Mock Step 2: enrich_with_concepts (模拟关联结果)
    # 假设: 000001=银行,深圳; 600519=白酒,消费; 000858=白酒; 600036=银行; 999999=华为
    def mock_enrich(df):
        logger.info("  [Mock] 关联概念...")
        tags_list = []
        all_tags = []
        for _, row in df.iterrows():
            code = row['ts_code']
            tags = []
            if code == '000001.SZ': tags = ['银行', '深圳', '金融科技']
            elif code == '600519.SH': tags = ['白酒', '大消费']
            elif code == '000858.SZ': tags = ['白酒', '深股通']
            elif code == '600036.SH': tags = ['银行', '沪股通']
            elif code == '999999.SZ': tags = ['华为', '消费电子']
            else: tags = ['其他']
            
            tags_list.append(",".join(tags))
            all_tags.extend(tags)
            
        df['concept_tags'] = tags_list
        return df, all_tags

    analyzer.enrich_with_concepts = MagicMock(side_effect=mock_enrich)
    
    # 运行复盘
    try:
        trade_date = '20241231'
        logger.info(f"开始执行 run_daily_replay({trade_date})...")
        
        result = analyzer.run_daily_replay(trade_date)
        
        if result['success']:
            logger.info("\n✅ Mock 测试成功！")
            stats = result['stats']
            logger.info(f"  - 主线概念: {stats['main_themes']}")
            logger.info(f"  - 涨停总数: {stats['total_limits']}")
            
            # 验证数据库是否真的写入了
            mgr = LanceDBManager(table_name="daily_limit_history")
            df_db = mgr.load_to_polars(start_date=trade_date, end_date=trade_date).to_pandas()
            if not df_db.empty:
                logger.info(f"  - 数据库验证: 成功读取 {len(df_db)} 条记录")
                print("\n数据预览:")
                print(df_db[['stock_name', 'concept_resonance', 'strength_score']].to_string(index=False))
            else:
                logger.error("  - 数据库验证失败: 未找到记录")
                
        else:
            logger.error(f"❌ Mock 测试失败: {result['error']}")
            
    except Exception as e:
        logger.error(f"执行异常: {e}", exc_info=True)

if __name__ == "__main__":
    run_mock_test()
