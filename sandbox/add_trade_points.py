"""
批量添加买卖点到自选监控
根据用户提供的策略分析设置监控条件
"""
import sys
sys.path.insert(0, '.')

import requests

WATCHLIST_ITEMS = [
    # 第一阵营：形态优良，均线多头共振（优先监控买点）
    {
        "stock_code": "603876",
        "stock_name": "鼎胜新材",
        "buy_target_price": 19.39,  # 回踩5日线附近
        "notes": "放量突破平台创出新高，均线多头排列。等待回踩5日线不破作为右侧买点。止损：买入价下浮7%。",
        "tags": ["第一阵营", "主升浪", "均线多头"],
        "conditions": [
            {"key": "ma5_break_up", "enabled": True, "params": {}},
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "002922",
        "stock_name": "伊戈尔",
        "buy_target_price": 43.97,  # 回踩5日线
        "notes": "稳健向上的主升浪通道。缩量回踩5日线(43.97)或10日线(42.79)是较好的盈亏比介入点。不建议追高。",
        "tags": ["第一阵营", "主升浪"],
        "conditions": [
            {"key": "ma5_break_up", "enabled": True, "params": {}},
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "601233",
        "stock_name": "桐昆股份",
        "buy_target_price": 23.04,  # 5日线附近
        "notes": "大斜率拉升后首次明显回调，刚好踩在5日线。观察节后在5日线位置的承接力，收企稳阳线可右侧试仓。",
        "tags": ["第一阵营", "回调买入"],
        "conditions": [
            {"key": "ma5_break_up", "enabled": True, "params": {}},
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    # 第二阵营：乖离率过大或遭遇高波重挫（需等待均值回归）
    {
        "stock_code": "603186",
        "stock_name": "华正新材",
        "sell_target_price": 74.34,  # 最高价82.60回撤10%止盈
        "notes": "抛物线加速主升浪，乖离率极大(距10日线超11%)。绝对禁止买入。若浮盈超20%，跌破74.34无条件止盈。",
        "tags": ["第二阵营", "乖离率大", "持仓止盈"],
        "conditions": [
            {"key": "ma_bear_alignment", "enabled": True, "params": {}},
            {"key": "ma20_break_down", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "600875",
        "stock_name": "东方电气",
        "buy_target_price": 28.52,  # 10日线附近
        "notes": "主升浪中途遭遇单日暴击(-5.32%)。暂缓操作，等待10日线(28.52)附近能否稳住并构筑新平台。",
        "tags": ["第二阵营", "等待企稳"],
        "conditions": [
            {"key": "ma10_break_up", "enabled": True, "params": {}},
            {"key": "ma20_break_up", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "002810",
        "stock_name": "山东赫达",
        "buy_target_price": 19.07,  # 10日线附近
        "notes": "高位急跌(-4.35%)，已击穿5日线，逼近10日线。短线退潮，暂无买点。等待止跌K线出现后再评估。",
        "tags": ["第二阵营", "等待止跌"],
        "conditions": [
            {"key": "ma10_break_up", "enabled": True, "params": {}},
            {"key": "rsi_oversold", "enabled": True, "params": {"threshold": 30}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
]


def add_watchlist_items():
    print("=" * 60)
    print("批量添加买卖点监控")
    print("=" * 60)
    
    url = "http://localhost:5000/api/portfolio/watchlist/batch"
    
    added_count = 0
    skipped_count = 0
    
    for item in WATCHLIST_ITEMS:
        print(f"\n处理: {item['stock_code']} - {item['stock_name']}")
        print(f"  买点: {item.get('buy_target_price', '-')}")
        print(f"  卖点: {item.get('sell_target_price', '-')}")
        print(f"  条件: {len(item.get('conditions', []))} 个")
        
        try:
            response = requests.post("http://localhost:5000/api/portfolio/watchlist", json=item)
            result = response.json()
            
            if result.get('success'):
                print(f"  ✓ 添加成功 (ID: {result['data'].get('id')})")
                added_count += 1
            else:
                if '已存在' in str(result.get('error', '')):
                    print(f"  - 已存在，跳过")
                    skipped_count += 1
                else:
                    print(f"  ✗ 添加失败: {result.get('error')}")
        except Exception as e:
            print(f"  ✗ 请求失败: {e}")
    
    print("\n" + "=" * 60)
    print(f"完成: 添加 {added_count} 只, 跳过 {skipped_count} 只")
    print("=" * 60)


if __name__ == "__main__":
    add_watchlist_items()
