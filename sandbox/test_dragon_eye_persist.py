"""
测试 DragonEye 数据入库功能
验证数据是否能正确写入 ArcticDB 并被读取
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "server"))

from core.dragon_eye.service import DragonEyeService
from core.dragon_eye.manager import DragonEyeManager
import pandas as pd


def test_persist_single_date(target_date: str):
    """
    测试单个日期的数据入库
    
    Args:
        target_date: 目标日期 (YYYY-MM-DD)
    """
    service = DragonEyeService()
    manager = DragonEyeManager()
    
    data_lake_dir = service.data_lake_dir / target_date
    
    print(f"\n{'='*60}")
    print(f"测试日期: {target_date}")
    print(f"数据目录: {data_lake_dir}")
    print(f"{'='*60}")
    
    # 检查数据文件是否存在
    sentiment_path = data_lake_dir / "market_sentiment_cycle.json"
    limit_up_path = data_lake_dir / "limit_up_filter.json"
    
    print(f"\n数据文件检查:")
    print(f"  - market_sentiment_cycle.json: {'✓ 存在' if sentiment_path.exists() else '✗ 不存在'}")
    print(f"  - limit_up_filter.json: {'✓ 存在' if limit_up_path.exists() else '✗ 不存在'}")
    
    if not sentiment_path.exists() and not limit_up_path.exists():
        print(f"\n错误: 数据文件不存在，请先运行爬虫")
        return False
    
    # 执行入库
    print(f"\n开始入库...")
    output_dir = service.cleaned_data_dir / target_date
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        service._persist_to_db(target_date, output_dir)
        print(f"✓ 入库完成")
    except Exception as e:
        print(f"✗ 入库失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 验证数据是否写入成功
    print(f"\n验证数据...")
    
    # 读取市场情绪数据
    sentiment_df = manager.get_market_sentiment(target_date, target_date)
    print(f"\n市场情绪数据:")
    if sentiment_df.is_empty():
        print(f"  ✗ 无数据")
    else:
        print(f"  ✓ 共 {len(sentiment_df)} 条记录")
        print(f"  列: {sentiment_df.columns}")
        for col in ['trade_date', 'limit_up_count', 'max_height', 'broken_ratio']:
            if col in sentiment_df.columns:
                print(f"  - {col}: {sentiment_df[col].to_list()}")
    
    # 读取龙头股数据
    stocks_df = manager.get_historical_dragon(target_date, target_date)
    print(f"\n龙头股数据:")
    if stocks_df.is_empty():
        print(f"  ✗ 无数据")
    else:
        print(f"  ✓ 共 {len(stocks_df)} 条记录")
        print(f"  列: {stocks_df.columns}")
        # 显示前3条
        for i, row in enumerate(stocks_df.head(3).to_dicts()):
            print(f"  [{i+1}] {row.get('stock_code', 'N/A')} {row.get('stock_name', 'N/A')} - {row.get('continue_num', 0)}连板")
    
    return not sentiment_df.is_empty() or not stocks_df.is_empty()


def test_query_api():
    """测试 API 查询"""
    import requests
    
    base_url = "http://localhost:5000"
    
    print(f"\n{'='*60}")
    print(f"测试 API 接口")
    print(f"{'='*60}")
    
    # 测试涨停趋势接口
    try:
        resp = requests.get(f"{base_url}/api/dragon/limit-up-trend", params={
            "start_date": "2026-02-01",
            "end_date": "2026-02-20"
        }, timeout=5)
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"\n/limit-up-trend 接口:")
            print(f"  dates: {data.get('dates', [])[:5]}...")
            print(f"  limit_up_counts: {data.get('limit_up_counts', [])[:5]}...")
            print(f"  max_heights: {data.get('max_heights', [])[:5]}...")
        else:
            print(f"\n/limit-up-trend 接口失败: {resp.status_code}")
    except Exception as e:
        print(f"\n/limit-up-trend 接口异常: {e}")
    
    # 测试龙头股接口
    try:
        resp = requests.get(f"{base_url}/api/dragon/stocks", params={
            "start_date": "2026-02-12",
            "end_date": "2026-02-12"
        }, timeout=5)
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"\n/stocks 接口:")
            print(f"  返回 {len(data)} 条记录")
            if data:
                print(f"  第一条: {data[0].get('stock_code', 'N/A')} {data[0].get('stock_name', 'N/A')}")
        else:
            print(f"\n/stocks 接口失败: {resp.status_code}")
    except Exception as e:
        print(f"\n/stocks 接口异常: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="测试 DragonEye 数据入库")
    parser.add_argument("--date", default="2026-02-12", help="目标日期 (YYYY-MM-DD)")
    parser.add_argument("--api", action="store_true", help="测试 API 接口")
    
    args = parser.parse_args()
    
    if args.api:
        test_query_api()
    else:
        success = test_persist_single_date(args.date)
        sys.exit(0 if success else 1)
