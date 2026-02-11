# data_svc/concept_data_loader.py
"""
股票概念数据加载器

从 Tushare 获取股票-概念映射关系，构建本地概念知识库
用于支持 Daily Resonance Replay 模块的概念共振分析
"""
import os
import sys
import time
from typing import Dict, List, Optional, Set
from datetime import datetime
from collections import defaultdict

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

logger = get_logger(__name__)

# Tushare 频控配置 (与 tushare_updater.py 保持一致)
RATE_LIMIT_PER_MINUTE = 500
_WINDOW_SECONDS = 60
from collections import deque
_request_records = deque()


def call_with_rate_limit(api_callable, *args, **kwargs):
    """确保 API 调用遵循每分钟最多 500 次的限制"""
    global _request_records
    now = time.time()
    
    # 清理超过窗口期的记录
    while _request_records and (now - _request_records[0]) > _WINDOW_SECONDS:
        _request_records.popleft()
    
    # 如果达到限制，等待
    if len(_request_records) >= RATE_LIMIT_PER_MINUTE:
        sleep_time = _WINDOW_SECONDS - (now - _request_records[0]) + 0.1
        if sleep_time > 0:
            logger.info(f"达到频率限制，等待 {sleep_time:.1f} 秒...")
            time.sleep(sleep_time)
            _request_records.clear()
    
    # 记录本次请求
    _request_records.append(time.time())
    
    # 执行调用
    return api_callable(*args, **kwargs)


class ConceptDataLoader:
    """概念数据加载器"""
    
    def __init__(self, tushare_token: Optional[str] = None):
        """
        初始化概念数据加载器
        
        Args:
            tushare_token: Tushare API Token (如果不提供，从环境变量读取)
        """
        # 获取 Tushare Token
        if tushare_token is None:
            tushare_token = getattr(Config, 'TUSHARE_TOKEN', None)
            if tushare_token is None:
                raise ValueError("未找到 Tushare Token，请在 Config 中配置或传入参数")
        
        self.pro = ts.pro_api(tushare_token)
        self.lance_mgr = LanceDBManager(table_name="stock_concepts")
        logger.info("概念数据加载器初始化完成")
    
    def fetch_all_concepts(self, limit: Optional[int] = None) -> pd.DataFrame:
        """
        获取所有概念分类
        
        Args:
            limit: 限制获取数量（用于测试，None 表示获取全部）
            
        Returns:
            概念列表 DataFrame (columns: code, name, src)
        """
        logger.info("正在获取概念分类列表...")
        
        try:
            df_concepts = call_with_rate_limit(
                self.pro.concept,
                src='ts',  # 使用 Tushare 概念分类
                fields='code,name,src'
            )
            
            if df_concepts.empty:
                logger.warning("未获取到概念数据")
                return pd.DataFrame()
            
            if limit:
                df_concepts = df_concepts.head(limit)
            
            logger.info(f"成功获取 {len(df_concepts)} 个概念分类")
            return df_concepts
            
        except Exception as e:
            logger.error(f"获取概念列表失败: {e}")
            raise
    
    def fetch_concept_stocks(self, concept_code: str, concept_name: str) -> List[Dict[str, str]]:
        """
        获取指定概念下的所有成分股
        
        Args:
            concept_code: 概念代码
            concept_name: 概念名称
            
        Returns:
            成分股列表 [{'ts_code': '000001.SZ', 'name': '平安银行'}, ...]
        """
        try:
            df_stocks = call_with_rate_limit(
                self.pro.concept_detail,
                id=concept_code,
                fields='ts_code,name'
            )
            
            if df_stocks.empty:
                return []
            
            # 添加概念名称
            stocks = df_stocks.to_dict('records')
            for stock in stocks:
                stock['concept'] = concept_name
            
            return stocks
            
        except Exception as e:
            logger.warning(f"获取概念 {concept_name}({concept_code}) 成分股失败: {e}")
            return []
    
    def build_concept_mapping(self, limit: Optional[int] = None, 
                             batch_save_interval: int = 10) -> Dict[str, List[str]]:
        """
        构建股票-概念映射关系
        
        Args:
            limit: 限制处理的概念数量（None 表示全部）
            batch_save_interval: 每处理多少个概念保存一次（防止中断丢失数据）
            
        Returns:
            股票概念映射字典 {'000001.SZ': ['银行', '深圳'], ...}
        """
        logger.info("🧠 开始构建概念知识图谱...")
        
        # 1. 获取所有概念
        df_concepts = self.fetch_all_concepts(limit=limit)
        if df_concepts.empty:
            logger.error("无法获取概念列表，终止构建")
            return {}
        
        total_concepts = len(df_concepts)
        logger.info(f"将处理 {total_concepts} 个概念分类")
        
        # 2. 遍历每个概念，获取成分股
        stock_tags_map = defaultdict(lambda: {'name': '', 'tags': []})
        
        with tqdm(total=total_concepts, desc="构建概念图谱") as pbar:
            for idx, row in df_concepts.iterrows():
                concept_code = row['code']
                concept_name = row['name']
                
                # 获取该概念下的成分股
                stocks = self.fetch_concept_stocks(concept_code, concept_name)
                
                # 更新映射
                for stock in stocks:
                    ts_code = stock['ts_code']
                    stock_tags_map[ts_code]['name'] = stock['name']
                    stock_tags_map[ts_code]['tags'].append(concept_name)
                
                pbar.update(1)
                pbar.set_postfix({'concept': concept_name, 'stocks': len(stocks)})
                
                # 定期保存（防止中断丢失数据）
                if (idx + 1) % batch_save_interval == 0:
                    self._save_partial_data(stock_tags_map)
                
                # 安全延迟（防止频控）
                time.sleep(0.2)
        
        logger.info(f"✓ 概念图谱构建完成，共 {len(stock_tags_map)} 只股票")
        return dict(stock_tags_map)
    
    def _save_partial_data(self, stock_tags_map: Dict) -> None:
        """保存部分数据（内部方法）"""
        try:
            df_save = self._convert_to_dataframe(stock_tags_map)
            if not df_save.empty:
                # 使用 upsert 模式（如果表已存在则更新）
                self._upsert_to_lancedb(df_save)
                logger.debug(f"已保存 {len(df_save)} 条记录")
        except Exception as e:
            logger.warning(f"部分数据保存失败: {e}")
    
    def _convert_to_dataframe(self, stock_tags_map: Dict) -> pd.DataFrame:
        """将映射字典转换为 DataFrame"""
        data_list = []
        for ts_code, info in stock_tags_map.items():
            # 去重并转为逗号分隔字符串
            tags_str = ",".join(sorted(set(info['tags'])))
            
            # 提取标准化的 stock_code (去掉后缀)
            stock_code = ts_code.split('.')[0]
            
            data_list.append({
                'ts_code': ts_code,
                'stock_code': stock_code,
                'stock_name': info['name'],
                'concepts': tags_str,
                'update_date': datetime.now().strftime('%Y%m%d')
            })
        
        return pd.DataFrame(data_list)
    
    def _upsert_to_lancedb(self, df: pd.DataFrame) -> None:
        """写入或更新 LanceDB"""
        try:
            # 检查表是否存在
            table_exists = "stock_concepts" in self.lance_mgr.db.table_names()
            
            if not table_exists:
                # 创建新表
                logger.info("创建 stock_concepts 表...")
                self.lance_mgr.db.create_table("stock_concepts", df)
            else:
                # 追加数据（LanceDB 会自动处理重复）
                table = self.lance_mgr.db.open_table("stock_concepts")
                table.add(df)
        
        except Exception as e:
            logger.error(f"写入 LanceDB 失败: {e}")
            raise
    
    def update_concepts_table(self, limit: Optional[int] = None, 
                             force_rebuild: bool = False) -> None:
        """
        更新概念表（主入口函数）
        
        Args:
            limit: 限制处理的概念数量（None 表示全部）
            force_rebuild: 是否强制重建表（删除旧数据）
        """
        logger.info("=" * 60)
        logger.info("开始更新股票概念表")
        logger.info("=" * 60)
        
        # 如果强制重建，删除旧表
        if force_rebuild:
            try:
                if "stock_concepts" in self.lance_mgr.db.table_names():
                    self.lance_mgr.db.drop_table("stock_concepts")
                    logger.info("已删除旧的 stock_concepts 表")
            except Exception as e:
                logger.warning(f"删除旧表失败: {e}")
        
        # 构建映射
        stock_tags_map = self.build_concept_mapping(limit=limit)
        
        if not stock_tags_map:
            logger.error("未获取到任何数据，更新失败")
            return
        
        # 转换并保存
        df_final = self._convert_to_dataframe(stock_tags_map)
        
        logger.info(f"正在保存 {len(df_final)} 条记录到 LanceDB...")
        self._upsert_to_lancedb(df_final)
        
        logger.info("=" * 60)
        logger.info(f"✓ 概念表更新完成！共 {len(df_final)} 只股票")
        logger.info("=" * 60)
        
        # 显示示例
        if not df_final.empty:
            logger.info("\n示例数据:")
            print(df_final.head(3).to_string())
    
    def get_stock_concepts(self, stock_code: str) -> Optional[List[str]]:
        """
        查询指定股票的概念标签
        
        Args:
            stock_code: 股票代码 (支持 '000001' 或 '000001.SZ' 格式)
            
        Returns:
            概念标签列表，如果未找到返回 None
        """
        try:
            # 标准化代码
            clean_code = stock_code.split('.')[0]
            
            # 查询 LanceDB
            df = self.lance_mgr.load_to_polars(
                stock_codes=[clean_code],
                columns=['stock_code', 'concepts']
            )
            
            if df.is_empty():
                return None
            
            # 解析概念字符串
            concepts_str = df['concepts'][0]
            if not concepts_str:
                return []
            
            return concepts_str.split(',')
            
        except Exception as e:
            logger.warning(f"查询股票 {stock_code} 概念失败: {e}")
            return None


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='股票概念数据加载器')
    parser.add_argument('--limit', type=int, default=None, 
                       help='限制处理的概念数量（测试用）')
    parser.add_argument('--rebuild', action='store_true',
                       help='强制重建表（删除旧数据）')
    parser.add_argument('--token', type=str, default=None,
                       help='Tushare API Token（可选）')
    
    args = parser.parse_args()
    
    try:
        loader = ConceptDataLoader(tushare_token=args.token)
        loader.update_concepts_table(limit=args.limit, force_rebuild=args.rebuild)
    except Exception as e:
        logger.error(f"执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
