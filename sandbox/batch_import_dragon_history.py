"""
批量导入 DragonEye 历史数据
将 data_lake 目录下的所有历史数据导入到 ArcticDB
"""
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "server"))

from core.dragon_eye.service import DragonEyeService
from core.dragon_eye.manager import DragonEyeManager


def batch_import_history(start_date: str = None, end_date: str = None):
    """
    批量导入历史数据
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD)，默认导入所有
        end_date: 结束日期 (YYYY-MM-DD)
    """
    service = DragonEyeService()
    manager = DragonEyeManager()
    
    data_lake_dir = service.data_lake_dir
    
    # 获取所有日期目录
    date_dirs = sorted([d for d in data_lake_dir.iterdir() if d.is_dir()])
    
    print(f"\n{'='*60}")
    print(f"批量导入 DragonEye 历史数据")
    print(f"数据目录: {data_lake_dir}")
    print(f"发现 {len(date_dirs)} 个日期目录")
    print(f"{'='*60}\n")
    
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    for date_dir in date_dirs:
        date_str = date_dir.name
        
        # 日期过滤
        if start_date and date_str < start_date:
            continue
        if end_date and date_str > end_date:
            continue
        
        # 检查必要文件是否存在
        sentiment_path = date_dir / "market_sentiment_cycle.json"
        limit_up_path = date_dir / "limit_up_filter.json"
        
        if not sentiment_path.exists() or not limit_up_path.exists():
            print(f"[跳过] {date_str} - 数据文件不完整")
            skip_count += 1
            continue
        
        # 检查是否已导入
        existing = manager.get_market_sentiment(date_str, date_str)
        if not existing.is_empty():
            print(f"[已存在] {date_str} - 跳过")
            skip_count += 1
            continue
        
        # 执行导入
        try:
            output_dir = service.cleaned_data_dir / date_str
            output_dir.mkdir(parents=True, exist_ok=True)
            
            service._persist_to_db(date_str, output_dir)
            print(f"[成功] {date_str}")
            success_count += 1
        except Exception as e:
            print(f"[失败] {date_str} - {e}")
            fail_count += 1
    
    print(f"\n{'='*60}")
    print(f"导入完成:")
    print(f"  成功: {success_count}")
    print(f"  失败: {fail_count}")
    print(f"  跳过: {skip_count}")
    print(f"{'='*60}\n")
    
    # 验证数据
    print("验证数据...")
    if start_date and end_date:
        sentiment_df = manager.get_market_sentiment(start_date, end_date)
        stocks_df = manager.get_historical_dragon(start_date, end_date)
        print(f"  市场情绪: {len(sentiment_df)} 条")
        print(f"  龙头股: {len(stocks_df)} 条")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="批量导入 DragonEye 历史数据")
    parser.add_argument("--start", default=None, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", default=None, help="结束日期 (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    batch_import_history(args.start, args.end)
