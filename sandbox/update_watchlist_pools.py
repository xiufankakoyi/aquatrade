"""
清理废弃池股票 + 更新监控策略
"""
import sys
sys.path.insert(0, '.')

import requests

# 废弃池C：趋势破位/左侧运行（直接剔除）
DISCARD_CODES = [
    # A杀/断头铡刀
    "601869",  # 长飞光纤
    "601975",  # 招商南油
    "600879",  # 航天电子
    "600026",  # 中远海能
    # 均线空头排列/左侧
    "600489",  # 中金黄金
    "600183",  # 生益科技
    "000636",  # 风华高科
    "002222",  # 福晶科技
    "002156",  # 通富微电
    "600584",  # 长电科技
    "600875",  # 东方电气
    "002810",  # 山东赫达
    # 高位杂乱震荡/动能衰退
    "002185",  # 华天科技
    "002916",  # 深南电路
    "001309",  # 德明利
    "002636",  # 金安国纪
]

# 核心池A：主升浪/龙头右侧标的（重点实操）
CORE_POOL_A = [
    {
        "stock_code": "600893",
        "stock_name": "航发动力",
        "notes": "核心池A：标准右侧加速，回踩5日线买入，11%止损过滤日内剧震。动态止盈：跌破5日线触发卖出信号。",
        "tags": ["核心池A", "主升浪", "龙头"],
        "conditions": [
            {"key": "ma5_break_down", "enabled": True, "params": {}},  # 跌破5日线止盈
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}  # 均线多头确认
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "600331",
        "stock_name": "宏达股份",
        "notes": "核心池A：稳健主升浪，10日线附近逢低拿货，11%止损容错率高。动态止盈：跌破10日线触发卖出信号。",
        "tags": ["核心池A", "主升浪"],
        "conditions": [
            {"key": "ma10_break_down", "enabled": True, "params": {}},  # 跌破10日线止盈
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "002028",
        "stock_name": "思源电气",
        "notes": "核心池A：慢牛标的，波动小，11%止损可做中长线波段。动态止盈：跌破10日线触发卖出信号。",
        "tags": ["核心池A", "慢牛"],
        "conditions": [
            {"key": "ma10_break_down", "enabled": True, "params": {}},
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "603986",
        "stock_name": "兆易创新",
        "notes": "核心池A：半导体右侧修复。动态止盈：跌破5日线触发卖出信号。",
        "tags": ["核心池A", "半导体", "右侧修复"],
        "conditions": [
            {"key": "ma5_break_down", "enabled": True, "params": {}},
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "603876",
        "stock_name": "鼎胜新材",
        "notes": "核心池A：放量突破平台新高，典型右侧突破买点。动态止盈：跌破5日线触发卖出信号。",
        "tags": ["核心池A", "突破", "主升浪"],
        "conditions": [
            {"key": "ma5_break_down", "enabled": True, "params": {}},
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "002922",
        "stock_name": "伊戈尔",
        "notes": "核心池A：依托均线稳步抬升，回踩均线分批建仓。动态止盈：跌破10日线触发卖出信号。",
        "tags": ["核心池A", "主升浪"],
        "conditions": [
            {"key": "ma10_break_down", "enabled": True, "params": {}},
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "601233",
        "stock_name": "桐昆股份",
        "notes": "核心池A：依托均线稳步抬升，回踩均线分批建仓。动态止盈：跌破10日线触发卖出信号。",
        "tags": ["核心池A", "主升浪"],
        "conditions": [
            {"key": "ma10_break_down", "enabled": True, "params": {}},
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
]

# 观察池B：高波剧震/乖离率过大（等待结构修复）
WATCH_POOL_B = [
    {
        "stock_code": "603186",
        "stock_name": "华正新材",
        "notes": "观察池B：极强主升浪但乖离率过大。等待自然回撤10%向均线靠拢再买，叠加11%止损防线。监控：均线多头确认。",
        "tags": ["观察池B", "乖离过大", "等待修复"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "ma10_break_down", "enabled": True, "params": {}}  # 跌破10日线止损
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "603256",
        "stock_name": "宏和科技",
        "notes": "观察池B：极强主升浪但乖离率过大。等待自然回撤10%向均线靠拢再买。监控：均线多头确认。",
        "tags": ["观察池B", "乖离过大", "等待修复"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "ma10_break_down", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "000657",
        "stock_name": "中钨高新",
        "notes": "观察池B：主升途中遭遇单日剧震大阴线。不急于接飞刀，等均线走平右侧确认企稳再进。",
        "tags": ["观察池B", "高波动", "等待企稳"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "ma10_break_down", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "600176",
        "stock_name": "中国巨石",
        "notes": "观察池B：主升途中遭遇单日剧震大阴线。不急于接飞刀，等均线走平右侧确认企稳再进。",
        "tags": ["观察池B", "高波动", "等待企稳"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "ma10_break_down", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "002080",
        "stock_name": "中材科技",
        "notes": "观察池B：主升途中遭遇单日剧震大阴线。不急于接飞刀，等均线走平右侧确认企稳再进。",
        "tags": ["观察池B", "高波动", "等待企稳"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "ma10_break_down", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "002625",
        "stock_name": "光启技术",
        "notes": "观察池B：宽幅震荡，等突破颈线即可右侧追入。监控：均线多头确认。",
        "tags": ["观察池B", "震荡", "等待突破"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "volume_surge", "enabled": True, "params": {"multiplier": 1.5}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
]


def delete_watchlist_item(stock_code: str) -> bool:
    """删除监控项"""
    try:
        response = requests.delete(f"http://localhost:5000/api/portfolio/watchlist/{stock_code}")
        return response.json().get('success', False)
    except:
        return False


def update_watchlist_item(item: dict) -> bool:
    """更新监控项（先删后增）"""
    stock_code = item['stock_code']
    delete_watchlist_item(stock_code)
    
    try:
        response = requests.post("http://localhost:5000/api/portfolio/watchlist", json=item)
        return response.json().get('success', False)
    except:
        return False


def main():
    print("=" * 60)
    print("清理废弃池 + 更新监控策略")
    print("=" * 60)
    
    # 1. 删除废弃池股票
    print("\n【废弃池C】删除以下股票监控：")
    for code in DISCARD_CODES:
        if delete_watchlist_item(code):
            print(f"  ✓ 已删除: {code}")
        else:
            print(f"  - 不存在: {code}")
    
    # 2. 更新核心池A
    print("\n【核心池A】更新监控：")
    for item in CORE_POOL_A:
        if update_watchlist_item(item):
            print(f"  ✓ {item['stock_code']} - {item['stock_name']}")
        else:
            print(f"  ✗ 失败: {item['stock_code']}")
    
    # 3. 更新观察池B
    print("\n【观察池B】更新监控：")
    for item in WATCH_POOL_B:
        if update_watchlist_item(item):
            print(f"  ✓ {item['stock_code']} - {item['stock_name']}")
        else:
            print(f"  ✗ 失败: {item['stock_code']}")
    
    print("\n" + "=" * 60)
    print("完成！动态止盈止损逻辑：")
    print("  - 核心池A：跌破5/10日线触发卖出信号")
    print("  - 观察池B：跌破10日线触发卖出信号")
    print("  - 止损线：11%")
    print("=" * 60)


if __name__ == "__main__":
    main()
