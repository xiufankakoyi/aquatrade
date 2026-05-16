"""
更新核心池A/B的监控条件为买入信号
"""
import sys
sys.path.insert(0, '.')

import requests

# 核心池A：监控买入机会
CORE_POOL_A_UPDATES = [
    {
        "stock_code": "600893",
        "stock_name": "航发动力",
        "notes": "核心池A：标准右侧加速，回踩5日线买入，11%止损过滤日内剧震。",
        "tags": ["核心池A", "主升浪", "龙头"],
        "conditions": [
            {"key": "ma5_break_up", "enabled": True, "params": {}},  # 突破5日线=买入信号
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "600331",
        "stock_name": "宏达股份",
        "notes": "核心池A：稳健主升浪，10日线附近逢低拿货，容错率极高。",
        "tags": ["核心池A", "主升浪"],
        "conditions": [
            {"key": "ma10_break_up", "enabled": True, "params": {}},  # 突破10日线=买入信号
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "002028",
        "stock_name": "思源电气",
        "notes": "核心池A：慢牛标的，波动小，11%止损可做中长线波段。",
        "tags": ["核心池A", "慢牛"],
        "conditions": [
            {"key": "ma10_break_up", "enabled": True, "params": {}},
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "603986",
        "stock_name": "兆易创新",
        "notes": "核心池A：半导体右侧修复。回踩5日线买入。",
        "tags": ["核心池A", "半导体", "右侧修复"],
        "conditions": [
            {"key": "ma5_break_up", "enabled": True, "params": {}},
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "603876",
        "stock_name": "鼎胜新材",
        "notes": "核心池A：放量突破平台新高，典型右侧突破买点。回踩5日线买入。",
        "tags": ["核心池A", "突破", "主升浪"],
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
        "notes": "核心池A：依托均线稳步抬升，回踩10日线分批建仓。",
        "tags": ["核心池A", "主升浪"],
        "conditions": [
            {"key": "ma10_break_up", "enabled": True, "params": {}},
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "601233",
        "stock_name": "桐昆股份",
        "notes": "核心池A：依托均线稳步抬升，回踩10日线分批建仓。",
        "tags": ["核心池A", "主升浪"],
        "conditions": [
            {"key": "ma10_break_up", "enabled": True, "params": {}},
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
]

# 观察池B：监控企稳买入机会
WATCH_POOL_B_UPDATES = [
    {
        "stock_code": "603186",
        "stock_name": "华正新材",
        "notes": "观察池B：极强主升浪但乖离率过大。等待自然回撤10%向均线靠拢再买，叠加11%止损防线。",
        "tags": ["观察池B", "乖离过大", "等待修复"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "ma10_break_up", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "603256",
        "stock_name": "宏和科技",
        "notes": "观察池B：极强主升浪但乖离率过大。等待自然回撤10%向均线靠拢再买。",
        "tags": ["观察池B", "乖离过大", "等待修复"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "ma10_break_up", "enabled": True, "params": {}}
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
            {"key": "ma10_break_up", "enabled": True, "params": {}}
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
            {"key": "ma10_break_up", "enabled": True, "params": {}}
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
            {"key": "ma10_break_up", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "002625",
        "stock_name": "光启技术",
        "notes": "观察池B：宽幅震荡，等突破颈线即可右侧追入。",
        "tags": ["观察池B", "震荡", "等待突破"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "volume_surge", "enabled": True, "params": {"multiplier": 1.5}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
]


def update_watchlist_item(item: dict) -> bool:
    """更新监控项（先删后增）"""
    stock_code = item['stock_code']
    
    try:
        requests.delete(f"http://localhost:5000/api/portfolio/watchlist/{stock_code}")
    except:
        pass
    
    try:
        response = requests.post("http://localhost:5000/api/portfolio/watchlist", json=item)
        return response.json().get('success', False)
    except:
        return False


def main():
    print("=" * 60)
    print("更新监控条件为买入信号")
    print("=" * 60)
    
    print("\n【核心池A】更新买入条件：")
    for item in CORE_POOL_A_UPDATES:
        if update_watchlist_item(item):
            print(f"  ✓ {item['stock_code']} - {item['stock_name']}")
        else:
            print(f"  ✗ 失败: {item['stock_code']}")
    
    print("\n【观察池B】更新买入条件：")
    for item in WATCH_POOL_B_UPDATES:
        if update_watchlist_item(item):
            print(f"  ✓ {item['stock_code']} - {item['stock_name']}")
        else:
            print(f"  ✗ 失败: {item['stock_code']}")
    
    print("\n" + "=" * 60)
    print("监控逻辑说明：")
    print("  - 核心池A/B：监控买入机会（均线支撑确认）")
    print("  - 突破5日线/10日线 = 回踩后重新站上 = 买入信号")
    print("  - 止损线：11%")
    print("=" * 60)


if __name__ == "__main__":
    main()
