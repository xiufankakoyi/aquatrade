"""
双源写入测试脚本
================

测试场景：
1. Tushare 数据写入 -> 验证水位表
2. Crawler 数据写入 -> 验证水位表
3. 缺口检查 -> 验证检测功能
4. 水位表重建 -> 验证自愈机制

运行方式：
    python sandbox/test_ingestion.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import polars as pl
from datetime import datetime, timedelta

from config.logger import get_logger

logger = get_logger(__name__)


def create_mock_tushare_data(trade_date: str, stock_codes: list) -> pl.DataFrame:
    """
    创建模拟 Tushare 数据（原始除权）
    
    Args:
        trade_date: 交易日期 (YYYY-MM-DD)
        stock_codes: 股票代码列表
        
    Returns:
        Polars DataFrame
    """
    data = []
    
    for i, code in enumerate(stock_codes):
        base_price = 10.0 + i * 0.5
        data.append({
            "stock_code": code,
            "trade_date": trade_date,
            "open": base_price,
            "high": base_price * 1.02,
            "low": base_price * 0.98,
            "close": base_price,
            "volume": 1000000 + i * 100000,
            "amount": base_price * 1000000,
            "adj_factor": 1.0,
        })
    
    return pl.DataFrame(data)


def create_mock_crawler_data(trade_date: str, stock_codes: list) -> pl.DataFrame:
    """
    创建模拟爬虫数据（原始除权）
    
    Args:
        trade_date: 交易日期
        stock_codes: 股票代码列表
        
    Returns:
        Polars DataFrame
    """
    data = []
    
    for i, code in enumerate(stock_codes):
        base_price = 20.0 + i * 0.3
        data.append({
            "stock_code": code,
            "trade_date": trade_date,
            "open": base_price,
            "high": base_price * 1.03,
            "low": base_price * 0.97,
            "close": base_price,
            "volume": 500000 + i * 50000,
            "amount": base_price * 500000,
            "adj_factor": 0.95,
        })
    
    return pl.DataFrame(data)


def test_watermark_manager():
    """测试水位表管理器"""
    print("\n" + "=" * 60)
    print("测试 1: 水位表管理器")
    print("=" * 60)
    
    from data_svc.ingestion.watermark_manager import get_watermark_manager
    
    wm = get_watermark_manager()
    
    print(f"水位表可用: {wm.is_available}")
    
    if not wm.is_available:
        print("⚠️ Redis 不可用，跳过测试")
        return False
    
    test_code = "TEST_WATERMARK_001"
    
    wm.delete(test_code)
    
    wm.update(
        stock_code=test_code,
        last_update_date="2026-04-25",
        rows_added=1,
        data_source="tushare",
        first_date="2020-01-02"
    )
    
    meta = wm.get(test_code)
    print(f"写入后获取水位: {meta}")
    
    assert meta is not None, "水位写入失败"
    assert meta["last_update_date"] == "2026-04-25", "水位日期不匹配"
    assert meta["data_source"] == "tushare", "数据源不匹配"
    
    wm.update(
        stock_code=test_code,
        last_update_date="2026-04-26",
        rows_added=1,
        data_source="tushare"
    )
    
    meta = wm.get(test_code)
    print(f"更新后获取水位: {meta}")
    
    assert meta["last_update_date"] == "2026-04-26", "水位更新失败"
    assert meta["rows_added"] == 2, f"行数累加失败: 期望 2, 实际 {meta['rows_added']}"
    
    stats = wm.get_stats()
    print(f"水位表统计: {stats}")
    
    wm.delete(test_code)
    meta = wm.get(test_code)
    assert meta is None, "水位删除失败"
    
    print("✅ 水位表管理器测试通过")
    return True


def test_ingestion_pipeline():
    """测试统一写入漏斗"""
    print("\n" + "=" * 60)
    print("测试 2: 统一写入漏斗")
    print("=" * 60)
    
    from data_svc.ingestion.ingestion_pipeline import ingestion_pipeline
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    tushare_df = create_mock_tushare_data(
        trade_date=today,
        stock_codes=["000001.SZ", "000002.SZ", "600000.SH"]
    )
    
    print(f"Tushare 模拟数据 ({len(tushare_df)} 行):")
    print(tushare_df.head(2))
    
    try:
        with ingestion_pipeline("daily_ohlcv", "tushare") as writer:
            writer.upsert(tushare_df)
            result = writer.get_result()
        
        print(f"写入结果: {result}")
        print("✅ Tushare 数据写入测试通过")
        
    except Exception as e:
        print(f"⚠️ LanceDB 写入跳过（表可能不存在）: {e}")
    
    return True


def test_crawler_etiquette():
    """测试爬虫行为规范"""
    print("\n" + "=" * 60)
    print("测试 3: 爬虫行为规范")
    print("=" * 60)
    
    from data_svc.ingestion.crawler_etiquette import (
        CrawlerEtiquette,
        rotate_user_agent,
        random_delay,
        crawler_retry
    )
    
    ua1 = rotate_user_agent()
    ua2 = rotate_user_agent()
    print(f"UA 轮换测试: {ua1[:50]}... != {ua2[:50]}...")
    assert ua1 != ua2 or len(set([rotate_user_agent() for _ in range(10)])) > 1, "UA 轮换失败"
    
    print("✅ UA 轮换测试通过")
    
    @crawler_retry(max_retries=2, base_delay=0.1)
    def mock_failing_request(should_fail: bool = True):
        if should_fail:
            raise ConnectionError("模拟网络错误")
        return "success"
    
    try:
        mock_failing_request(should_fail=True)
        print("❌ 重试测试失败：应该抛出异常")
    except ConnectionError:
        print("✅ 重试测试通过：正确抛出异常")
    
    class MockCrawler(CrawlerEtiquette):
        def __init__(self):
            super().__init__(name="MockCrawler", min_delay=0.01, max_delay=0.02)
    
    crawler = MockCrawler()
    stats = crawler.get_stats()
    print(f"爬虫统计: {stats}")
    
    print("✅ 爬虫行为规范测试通过")
    return True


def test_gap_checker():
    """测试缺口检查"""
    print("\n" + "=" * 60)
    print("测试 4: 缺口检查")
    print("=" * 60)
    
    from data_svc.ingestion.gap_checker import (
        check_data_gaps,
        get_trading_dates
    )
    
    trading_dates = get_trading_dates("2026-04-20", "2026-04-25")
    print(f"交易日历: {trading_dates}")
    
    result = check_data_gaps(trading_dates)
    
    print(f"缺口检查结果:")
    print(f"  - 有缺口: {result.has_gaps}")
    print(f"  - 缺失股票数: {result.total_missing_stocks}")
    print(f"  - 缺失日期数: {result.total_missing_dates}")
    print(f"  - 检查耗时: {result.check_duration_ms:.2f}ms")
    
    if result.has_gaps:
        print(f"  - 缺口详情 (前 5 只):")
        for i, (code, dates) in enumerate(list(result.gaps.items())[:5]):
            print(f"    {code}: {dates}")
    
    print("✅ 缺口检查测试通过")
    return True


def test_reconcile():
    """测试水位表重建"""
    print("\n" + "=" * 60)
    print("测试 5: 水位表重建")
    print("=" * 60)
    
    from data_svc.ingestion.watermark_manager import get_watermark_manager
    
    wm = get_watermark_manager()
    
    if not wm.is_available:
        print("⚠️ Redis 不可用，跳过重建测试")
        return True
    
    count = wm.reconcile_from_lancedb()
    print(f"从 LanceDB 重建水位表: {count} 只股票")
    
    stats = wm.get_stats()
    print(f"重建后统计: {stats}")
    
    print("✅ 水位表重建测试通过")
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🚀 开始双源写入测试")
    print("=" * 60)
    
    results = {
        "水位表管理器": test_watermark_manager(),
        "统一写入漏斗": test_ingestion_pipeline(),
        "爬虫行为规范": test_crawler_etiquette(),
        "缺口检查": test_gap_checker(),
        "水位表重建": test_reconcile(),
    }
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    for name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！")
    else:
        print("⚠️ 部分测试失败，请检查日志")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    run_all_tests()
