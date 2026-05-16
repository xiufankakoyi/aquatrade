"""
重新添加观察池C（趋势破位观察区）
"""
import sys
sys.path.insert(0, '.')

import requests

# 观察池C：趋势破位/左侧运行（观察修复情况）
WATCH_POOL_C = [
    # A杀/断头铡刀
    {
        "stock_code": "601869",
        "stock_name": "长飞光纤",
        "notes": "观察池C：主升浪遭遇断头铡刀式暴跌(-6%)，右侧趋势已破坏。观察修复情况，等待重新放量站上均线。",
        "tags": ["观察池C", "断头铡刀", "等待修复"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "volume_surge", "enabled": True, "params": {"multiplier": 2.0}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "601975",
        "stock_name": "招商南油",
        "notes": "观察池C：单日暴跌(-8.29%)击穿多条均线，短期右侧趋势彻底破坏。观察止跌企稳情况。",
        "tags": ["观察池C", "断头铡刀", "等待修复"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "rsi_oversold", "enabled": True, "params": {"threshold": 30}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "600879",
        "stock_name": "航天电子",
        "notes": "观察池C：从高点32.24见顶后陡峭下跌，均线空头排列。观察筑底情况。",
        "tags": ["观察池C", "A杀", "等待筑底"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "ma60_break_up", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "600026",
        "stock_name": "中远海能",
        "notes": "观察池C：放量大跌(-9.5%)击穿5日10日线。观察20日线或60日线能否企稳。",
        "tags": ["观察池C", "断头铡刀", "等待企稳"],
        "conditions": [
            {"key": "ma20_break_up", "enabled": True, "params": {}},
            {"key": "volume_surge", "enabled": True, "params": {"multiplier": 2.0}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    # 均线空头排列/左侧
    {
        "stock_code": "600489",
        "stock_name": "中金黄金",
        "notes": "观察池C：从高点41.48连续回落，均线空头排列，MACD死叉。观察筑底完成并突破长周期均线。",
        "tags": ["观察池C", "均线空头", "等待筑底"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "ma60_break_up", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "600183",
        "stock_name": "生益科技",
        "notes": "观察池C：从75.80高点回落后处于下降通道震荡，MACD水下死叉。等待重新放量站上所有均线。",
        "tags": ["观察池C", "下降通道", "等待反转"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "ma20_break_up", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "000636",
        "stock_name": "风华高科",
        "notes": "观察池C：单日重挫(-5.59%)，跌破5日线逼近10日线。观察20日线附近能否构筑双底。",
        "tags": ["观察池C", "趋势受损", "等待企稳"],
        "conditions": [
            {"key": "ma20_break_up", "enabled": True, "params": {}},
            {"key": "rsi_oversold", "enabled": True, "params": {"threshold": 30}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "002222",
        "stock_name": "福晶科技",
        "notes": "观察池C：高点76.00后连续回调，已跌穿5日线，MACD高位死叉。进入右侧下跌/调整周期。",
        "tags": ["观察池C", "高位回调", "等待企稳"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "ma20_break_up", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "002156",
        "stock_name": "通富微电",
        "notes": "观察池C：从59.20高位回落，已跌破多条重要均线，MACD水下死叉。右侧趋势已破坏。",
        "tags": ["观察池C", "趋势破位", "等待修复"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "ma60_break_up", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "600584",
        "stock_name": "长电科技",
        "notes": "观察池C：见顶54.63后急跌，K线被压制在多条均线之下。进入左侧调整期。",
        "tags": ["观察池C", "趋势破位", "等待修复"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "ma20_break_up", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "600875",
        "stock_name": "东方电气",
        "notes": "观察池C：主升浪中途遭遇单日暴击(-5.32%)，空头动能释放剧烈。观察10日线附近能否稳住。",
        "tags": ["观察池C", "单日暴击", "等待企稳"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "ma20_break_up", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "002810",
        "stock_name": "山东赫达",
        "notes": "观察池C：高位急跌(-4.35%)，已击穿5日线逼近10日线。短线退潮，等待止跌K线出现。",
        "tags": ["观察池C", "高位急跌", "等待止跌"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "rsi_oversold", "enabled": True, "params": {"threshold": 30}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    # 高位杂乱震荡/动能衰退
    {
        "stock_code": "002185",
        "stock_name": "华天科技",
        "notes": "观察池C：上涨后横盘震荡，均线高度粘合。方向不明，等待放量突破箱体顶部。",
        "tags": ["观察池C", "横盘震荡", "等待方向"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "volume_surge", "enabled": True, "params": {"multiplier": 2.0}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "002916",
        "stock_name": "深南电路",
        "notes": "观察池C：高位杂乱震荡，动能衰退。等待方向选择。",
        "tags": ["观察池C", "震荡", "等待方向"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "volume_surge", "enabled": True, "params": {"multiplier": 1.5}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "001309",
        "stock_name": "德明利",
        "notes": "观察池C：前期大幅回调后连续反弹，但受制于下行的20日线。属于下跌趋势中的次级反弹。",
        "tags": ["观察池C", "超跌反弹", "等待反转"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "ma20_break_up", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "002636",
        "stock_name": "金安国纪",
        "notes": "观察池C：高位箱体震荡回调，MACD零轴上方死叉。动能转弱，等待重新放量突破。",
        "tags": ["观察池C", "箱体震荡", "动能转弱"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "volume_surge", "enabled": True, "params": {"multiplier": 1.5}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
]


def add_watchlist_item(item: dict) -> bool:
    """添加监控项"""
    try:
        response = requests.post("http://localhost:5000/api/portfolio/watchlist", json=item)
        result = response.json()
        return result.get('success', False)
    except:
        return False


def main():
    print("=" * 60)
    print("重新添加观察池C（趋势破位观察区）")
    print("=" * 60)
    
    added_count = 0
    skipped_count = 0
    
    for item in WATCH_POOL_C:
        print(f"\n处理: {item['stock_code']} - {item['stock_name']}")
        print(f"  标签: {', '.join(item.get('tags', []))}")
        
        if add_watchlist_item(item):
            print(f"  ✓ 添加成功")
            added_count += 1
        else:
            print(f"  - 已存在或添加失败")
            skipped_count += 1
    
    print("\n" + "=" * 60)
    print(f"完成: 添加 {added_count} 只, 跳过 {skipped_count} 只")
    print("\n股票池分类：")
    print("  - 核心池A：主升浪/龙头右侧标的（重点实操）")
    print("  - 观察池B：高波剧震/乖离率过大（等待结构修复）")
    print("  - 观察池C：趋势破位/左侧运行（观察修复情况）")
    print("=" * 60)


if __name__ == "__main__":
    main()
