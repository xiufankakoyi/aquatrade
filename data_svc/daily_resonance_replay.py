# data_svc/daily_resonance_replay.py
"""
每日共振复盘模块 (Daily Resonance Replay)

核心功能：
1. 获取涨停"肌肉"数据 (limit_list_d)
2. 获取资金"血液"数据 (top_inst)
3. 关联概念"大脑"数据 (本地 stock_concepts)
4. 计算概念共振强度
5. 生成每日复盘报告并入库

输入：Target_Date (例如 "20241231")
输出：写入 daily_limit_history 表
"""
import os
import sys
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from collections import Counter

import pandas as pd
import tushare as ts
from tqdm import tqdm

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config.config import Config
from config.logger import get_logger
from data_svc.lance_manager import LanceDBManager
from data_svc.concept_data_loader import ConceptDataLoader, call_with_rate_limit

logger = get_logger(__name__)


class DailyResonanceReplay:
    """每日共振复盘分析器"""
    
    def __init__(self, tushare_token: Optional[str] = None):
        """
        初始化复盘分析器
        
        Args:
            tushare_token: Tushare API Token (如果不提供，从 Config 读取)
        """
        # 获取 Tushare Token
        if tushare_token is None:
            tushare_token = getattr(Config, 'TUSHARE_TOKEN', None)
            if tushare_token is None:
                raise ValueError("未找到 Tushare Token，请在 Config 中配置")
        
        self.pro = ts.pro_api(tushare_token)
        self.concept_loader = ConceptDataLoader(tushare_token=tushare_token)
        self.history_mgr = LanceDBManager(table_name="daily_limit_history")
        
        logger.info("每日共振复盘分析器初始化完成")
    
    def get_raw_market_data(self, trade_date: str) -> Tuple[pd.DataFrame, Dict[str, float]]:
        """
        Step 1: 获取原始"肌肉"与"血液"数据
        
        Args:
            trade_date: 交易日期 (格式: YYYYMMDD, 例如 "20241231")
            
        Returns:
            (涨停股票 DataFrame, 机构资金字典)
            
        Raises:
            ValueError: 如果无涨停数据或休市
        """
        logger.info(f"📊 Step 1: 获取 {trade_date} 的市场数据...")
        
        # 1. 获取涨停"肌肉"数据
        try:
            logger.info("  - 获取涨停列表 (limit_list_d)...")
            df_limits = call_with_rate_limit(
                self.pro.limit_list_d,
                trade_date=trade_date,
                limit_type='U'  # U=涨停, D=跌停
            )
            
            if df_limits is None or df_limits.empty:
                raise ValueError(f"今日无涨停数据，可能是休市或数据未更新 (日期: {trade_date})")
            
            logger.info(f"  ✓ 获取到 {len(df_limits)} 只涨停股票")
            
        except Exception as e:
            logger.error(f"获取涨停数据失败: {e}")
            raise
        
        # 2. 获取资金"血液"数据 (机构净买入)
        try:
            logger.info("  - 获取机构资金流向 (top_inst)...")
            df_inst = call_with_rate_limit(
                self.pro.top_inst,
                trade_date=trade_date
            )
            
            # 构建资金映射字典 (只保留净买入 > 0 的)
            smart_money_map = {}
            if df_inst is not None and not df_inst.empty:
                # 过滤净买入 > 0
                df_inst_positive = df_inst[df_inst['net_buy'] > 0]
                smart_money_map = dict(zip(
                    df_inst_positive['ts_code'],
                    df_inst_positive['net_buy']
                ))
                logger.info(f"  ✓ 获取到 {len(smart_money_map)} 只机构净买入股票")
            else:
                logger.warning("  ⚠️ 未获取到机构资金数据（可能是该日无龙虎榜）")
            
        except Exception as e:
            logger.warning(f"获取机构资金数据失败（非致命错误）: {e}")
            smart_money_map = {}
        
        return df_limits, smart_money_map
    
    def enrich_with_concepts(self, df_limits: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """
        Step 2: 关联"大脑" (本地概念库)
        
        Args:
            df_limits: 涨停股票 DataFrame
            
        Returns:
            (enriched_df, all_tags_pool)
            - enriched_df: 添加了 'concept_tags' 列的 DataFrame
            - all_tags_pool: 所有概念标签的列表（用于统计）
        """
        logger.info("🧠 Step 2: 关联概念库...")
        
        all_tags_pool = []
        concept_tags_list = []
        
        # 确保有 ts_code 列
        if 'ts_code' not in df_limits.columns:
            logger.error("涨停数据缺少 ts_code 列")
            raise ValueError("涨停数据格式错误")
        
        # 批量查询概念（优化性能）
        stock_codes = df_limits['ts_code'].tolist()
        
        logger.info(f"  - 查询 {len(stock_codes)} 只股票的概念标签...")
        
        # 使用 LanceDB 批量查询
        try:
            # 提取纯代码（去掉后缀）
            clean_codes = [code.split('.')[0] for code in stock_codes]
            
            # 查询概念表
            concepts_mgr = LanceDBManager(table_name="stock_concepts")
            df_concepts = concepts_mgr.load_to_polars(
                stock_codes=clean_codes,
                columns=['stock_code', 'concepts']
            ).to_pandas()
            
            # 构建映射字典
            concept_map = dict(zip(df_concepts['stock_code'], df_concepts['concepts']))
            
        except Exception as e:
            logger.warning(f"批量查询概念失败，使用逐个查询: {e}")
            concept_map = {}
        
        # 为每只股票分配概念标签
        for ts_code in stock_codes:
            clean_code = ts_code.split('.')[0]
            
            # 查找概念
            concepts_str = concept_map.get(clean_code, None)
            
            if concepts_str and pd.notna(concepts_str):
                # 解析概念字符串
                tags = [tag.strip() for tag in concepts_str.split(',') if tag.strip()]
            else:
                # 默认标签
                tags = ["未知/新股"]
            
            concept_tags_list.append(','.join(tags))
            all_tags_pool.extend(tags)
        
        # 添加概念列
        df_limits['concept_tags'] = concept_tags_list
        
        logger.info(f"  ✓ 概念关联完成，共收集 {len(all_tags_pool)} 个标签实例")
        
        return df_limits, all_tags_pool
    
    def calculate_resonance(self, all_tags_pool: List[str], 
                           total_limits: int) -> List[Tuple[str, int]]:
        """
        Step 3: 核心算法——计算"概念共振"
        
        定义主线：出现次数 > 3 且 占比 > 5% 的概念
        
        Args:
            all_tags_pool: 所有概念标签列表
            total_limits: 涨停股票总数
            
        Returns:
            sorted_themes: 排序后的主线列表 [("华为", 15), ("低空经济", 12), ...]
        """
        logger.info("⚡ Step 3: 计算概念共振强度...")
        
        # 1. 统计频率
        tag_counts = Counter(all_tags_pool)
        
        # 2. 筛选主线 (出现次数 > 3 且 占比 > 5%)
        main_themes = []
        threshold_count = 3
        threshold_ratio = 0.05
        
        for tag, count in tag_counts.items():
            ratio = count / total_limits if total_limits > 0 else 0
            
            if count > threshold_count and ratio > threshold_ratio:
                main_themes.append((tag, count))
        
        # 3. 排序（按频率降序）
        sorted_themes = sorted(main_themes, key=lambda x: x[1], reverse=True)
        
        # 日志输出
        if sorted_themes:
            logger.info(f"  ✓ 识别到 {len(sorted_themes)} 个主线概念:")
            for tag, count in sorted_themes[:5]:  # 只显示前5个
                ratio = count / total_limits * 100
                logger.info(f"    - {tag}: {count} 只 ({ratio:.1f}%)")
        else:
            logger.warning("  ⚠️ 未识别到明显的主线概念（可能是分散行情）")
        
        return sorted_themes
    
    def finalize_and_save(self, 
                         df_enriched: pd.DataFrame,
                         sorted_themes: List[Tuple[str, int]],
                         smart_money_map: Dict[str, float],
                         trade_date: str) -> Dict[str, Any]:
        """
        Step 4: 数据回填与入库
        
        Args:
            df_enriched: 已关联概念的涨停股票 DataFrame
            sorted_themes: 排序后的主线概念列表
            smart_money_map: 机构资金字典
            trade_date: 交易日期
            
        Returns:
            统计信息字典
        """
        logger.info("💾 Step 4: 数据整理与入库...")
        
        # 构建主线映射（用于快速查找）
        theme_rank_map = {tag: idx + 1 for idx, (tag, _) in enumerate(sorted_themes)}
        theme_set = set(theme_rank_map.keys())
        
        final_records = []
        
        for _, row in df_enriched.iterrows():
            ts_code = row['ts_code']
            stock_code = ts_code.split('.')[0]
            
            # A. 判定该股的主线归属
            # 逻辑：遍历该股的所有标签，找到排名最高的主线
            concept_tags = row['concept_tags'].split(',') if row['concept_tags'] else []
            
            best_match = "杂毛/独立逻辑"
            resonance_rank = 999  # 默认排名
            
            for tag in concept_tags:
                tag = tag.strip()
                if tag in theme_set:
                    # 找到主线，检查是否是最强的
                    rank = theme_rank_map[tag]
                    if rank < resonance_rank:
                        best_match = tag
                        resonance_rank = rank
            
            # B. 注入机构资金数据
            inst_net_buy = smart_money_map.get(ts_code, 0.0)
            
            # C. 计算强度打分 (封单额 / 流通市值)
            # 注意：Tushare limit_list_d 返回的字段可能不同，需要适配
            limit_amount = row.get('fd_amount', 0.0)  # 封单金额 (万元)
            circ_mv = row.get('circ_mv', 1.0)  # 流通市值 (万元)
            
            if circ_mv > 0:
                strength_score = limit_amount / circ_mv
            else:
                strength_score = 0.0
            
            # D. 构建记录
            record = {
                # 基本信息
                'stock_code': stock_code,
                'ts_code': ts_code,
                'stock_name': row.get('name', ''),
                'trade_date': trade_date,
                
                # 涨停详情
                'limit_times': row.get('limit_times', 1),  # 连板数
                'first_limit_time': row.get('first_time', ''),  # 首次涨停时间
                'last_limit_time': row.get('last_time', ''),  # 最后涨停时间
                'limit_amount': limit_amount,  # 封单金额
                'circ_mv': circ_mv,  # 流通市值
                
                # 概念共振 (核心特征)
                'concept_tags': row['concept_tags'],
                'concept_resonance': best_match,
                'resonance_rank': resonance_rank,
                
                # 机构资金
                'inst_net_buy': inst_net_buy,
                
                # 强度指标
                'strength_score': strength_score,
                
                # 其他有用字段
                'close': row.get('close', 0.0),
                'pct_chg': row.get('pct_chg', 0.0),
                'amount': row.get('amount', 0.0),  # 成交额
                'turnover_rate': row.get('turnover_rate', 0.0),  # 换手率
            }
            
            final_records.append(record)
        
        # 转换为 DataFrame
        df_final = pd.DataFrame(final_records)
        
        # 添加复合 ID
        df_final['_id'] = df_final['stock_code'] + '_' + trade_date
        
        # 写入 LanceDB
        logger.info(f"  - 写入 {len(df_final)} 条记录到 daily_limit_history...")
        
        try:
            # 检查表是否存在
            table_exists = "daily_limit_history" in self.history_mgr.db.table_names()
            
            if not table_exists:
                # 创建新表
                self.history_mgr.db.create_table("daily_limit_history", df_final)
                logger.info("  ✓ 创建 daily_limit_history 表")
            else:
                # 追加数据
                table = self.history_mgr.db.open_table("daily_limit_history")
                table.add(df_final)
                logger.info("  ✓ 数据追加成功")
        
        except Exception as e:
            logger.error(f"写入数据库失败: {e}")
            raise
        
        # 统计信息
        stats = {
            'trade_date': trade_date,
            'total_limits': len(df_final),
            'main_themes': sorted_themes[:5],  # 前5个主线
            'inst_coverage': sum(1 for r in final_records if r['inst_net_buy'] > 0),
            'avg_strength': df_final['strength_score'].mean(),
        }
        
        return stats
    
    def run_daily_replay(self, trade_date: str) -> Dict[str, Any]:
        """
        执行每日复盘（主入口函数）
        
        Args:
            trade_date: 交易日期 (格式: YYYYMMDD)
            
        Returns:
            分析结果字典
        """
        logger.info("=" * 70)
        logger.info(f"🚀 开始每日共振复盘: {trade_date}")
        logger.info("=" * 70)
        
        start_time = time.time()
        
        try:
            # Step 1: 获取原始数据
            df_limits, smart_money_map = self.get_raw_market_data(trade_date)
            
            # Step 2: 关联概念
            df_enriched, all_tags_pool = self.enrich_with_concepts(df_limits)
            
            # Step 3: 计算共振
            sorted_themes = self.calculate_resonance(all_tags_pool, len(df_limits))
            
            # Step 4: 入库
            stats = self.finalize_and_save(
                df_enriched, 
                sorted_themes, 
                smart_money_map, 
                trade_date
            )
            
            elapsed = time.time() - start_time
            
            # 输出总结
            logger.info("=" * 70)
            logger.info("✅ 复盘完成！")
            logger.info(f"  - 涨停股票: {stats['total_limits']} 只")
            logger.info(f"  - 主线概念: {[f'{t}({c})' for t, c in stats['main_themes']]}")
            logger.info(f"  - 机构覆盖: {stats['inst_coverage']} 只")
            logger.info(f"  - 平均强度: {stats['avg_strength']:.4f}")
            logger.info(f"  - 耗时: {elapsed:.2f} 秒")
            logger.info("=" * 70)
            
            return {
                'success': True,
                'stats': stats,
                'elapsed': elapsed
            }
        
        except Exception as e:
            logger.error(f"❌ 复盘失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='每日共振复盘分析')
    parser.add_argument('date', type=str, help='交易日期 (格式: YYYYMMDD)')
    parser.add_argument('--token', type=str, default=None, help='Tushare API Token')
    
    args = parser.parse_args()
    
    try:
        analyzer = DailyResonanceReplay(tushare_token=args.token)
        result = analyzer.run_daily_replay(args.date)
        
        if not result['success']:
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
