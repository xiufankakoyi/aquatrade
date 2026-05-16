"""
批量添加买卖点监控 - 第二批
根据用户提供的策略分析设置监控条件
"""
import sys
sys.path.insert(0, '.')

import requests

WATCHLIST_ITEMS = [
    # 第一梯队：趋势结构良好，可寻找右侧买点
    {
        "stock_code": "600893",
        "stock_name": "航发动力",
        "buy_target_price": 51.50,  # 回踩5日线
        "notes": "放量涨停，均线多头发散，MACD金叉。最佳右侧买点是突破后的首次缩量回踩5日线。止损7%，浮盈20%后启动移动止盈(最高价回撤10%)。",
        "tags": ["第一梯队", "主升浪加速", "涨停"],
        "conditions": [
            {"key": "ma5_break_up", "enabled": True, "params": {}},
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "macd_golden_cross", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "600331",
        "stock_name": "宏达股份",
        "buy_target_price": 17.15,  # 回踩5日线
        "notes": "均线完美多头排列，MACD金叉，主升浪加速阶段。等待缩量回踩5日线(17.15)或10日线(16.66)企稳介入。止损7%。",
        "tags": ["第一梯队", "主升浪", "均线多头"],
        "conditions": [
            {"key": "ma5_break_up", "enabled": True, "params": {}},
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "002028",
        "stock_name": "思源电气",
        "buy_target_price": 201.65,  # 回踩10日线
        "sell_target_price": 199.35,  # 高点回撤10%止盈
        "notes": "长期慢牛主升浪，创出221.50新高后回撤。等待10日线(201.65)或20日线(196.79)附近企稳。浮盈者关注高点回撤10%止盈线(199.35)。",
        "tags": ["第一梯队", "慢牛", "高位回撤"],
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
        "buy_target_price": 295.88,  # 5日线附近
        "notes": "企稳站上5日和10日均线，60日线稳步向上，主升浪结构未破坏。等待5日线附近缩量震荡介入，或放量突破前高331.07跟进。止损7%。",
        "tags": ["第一梯队", "趋势良好", "芯片"],
        "conditions": [
            {"key": "ma5_break_up", "enabled": True, "params": {}},
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    # 第二梯队：观望/等待企稳
    {
        "stock_code": "600026",
        "stock_name": "中远海能",
        "buy_target_price": 15.79,  # 20日线附近
        "notes": "放量大跌(-9.5%)击穿5日10日线，破坏短线趋势。等待20日线(15.79)或60日线企稳，重新放量突破大阴线二分之一(约17.70)才可介入。持仓者应已触发7%止损。",
        "tags": ["第二梯队", "等待企稳", "航运"],
        "conditions": [
            {"key": "ma20_break_up", "enabled": True, "params": {}},
            {"key": "volume_surge", "enabled": True, "params": {"multiplier": 2.0}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "002625",
        "stock_name": "光启技术",
        "buy_target_price": 50.00,  # 突破颈线位
        "notes": "高位回落宽幅震荡，均线粘合纠缠，MACD零轴下方。等待放量突破50元颈线位，且多头排列重新形成时才符合右侧买点。",
        "tags": ["第二梯队", "震荡整理", "等待突破"],
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
        "buy_target_price": 259.86,  # 20日线
        "notes": "前期大幅回调后连续反弹，突破5日10日线但受制于下行的20日线。属于下跌趋势中的次级反弹，等待突破并站稳20日线，均线重新走平向上发散。",
        "tags": ["第二梯队", "超跌反弹", "等待反转"],
        "conditions": [
            {"key": "ma20_break_up", "enabled": True, "params": {}},
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    # 第三梯队：乖离过大或高位震荡
    {
        "stock_code": "603256",
        "stock_name": "宏和科技",
        "sell_target_price": 69.09,  # 最高价76.77回撤10%止盈
        "notes": "极强主升浪加速期，但乖离率过大(距5日线近9%)。当前绝对无买点。持仓者：浮盈>20%执行最高价回撤10%动态止盈，触发线69.09。",
        "tags": ["第三梯队", "乖离过大", "持仓止盈"],
        "conditions": [
            {"key": "ma_bear_alignment", "enabled": True, "params": {}},
            {"key": "ma20_break_down", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "000657",
        "stock_name": "中钨高新",
        "buy_target_price": 51.00,  # 5日线
        "notes": "主升浪中途单日巨震(-5.28%)，收长上影线阴线但仍站5日线。波动率过大暂不介入，等待5日线(51.00)或10日线(48.79)缩量止跌并反包长上影线。",
        "tags": ["第三梯队", "高位震荡", "观望"],
        "conditions": [
            {"key": "ma5_break_up", "enabled": True, "params": {}},
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "002636",
        "stock_name": "金安国纪",
        "buy_target_price": 24.73,  # 10日线
        "notes": "高位箱体震荡回调，踩在5日线上，MACD零轴上方死叉。动能转弱，等待回踩10日线(24.73)或20日线(24.39)支撑，重新放量突破26元才是右侧时机。",
        "tags": ["第三梯队", "箱体震荡", "动能转弱"],
        "conditions": [
            {"key": "ma10_break_up", "enabled": True, "params": {}},
            {"key": "volume_surge", "enabled": True, "params": {"multiplier": 1.5}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "600176",
        "stock_name": "中国巨石",
        "sell_target_price": 25.04,  # 最高价27.83回撤10%止盈
        "notes": "陡直加速上涨后惨遭暴击(-6.37%)。无买点，单日跌幅已接近止损空间。持仓者：浮盈>20%执行动态止盈，触发线25.04。",
        "tags": ["第三梯队", "高位暴跌", "持仓止盈"],
        "conditions": [
            {"key": "ma_bear_alignment", "enabled": True, "params": {}},
            {"key": "ma20_break_down", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "002080",
        "stock_name": "中材科技",
        "buy_target_price": 42.19,  # 10日线
        "notes": "主升浪中途遭遇-4.13%大阴线，但仍维持5日线上方。波动过大暂缓买入，等待10日线(42.19)或20日线(41.23)缩量止跌，收出反包阴线的实体阳线。",
        "tags": ["第三梯队", "高位震荡", "观望"],
        "conditions": [
            {"key": "ma10_break_up", "enabled": True, "params": {}},
            {"key": "ma_bull_alignment", "enabled": True, "params": {}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "000636",
        "stock_name": "风华高科",
        "buy_target_price": 20.92,  # 20日线
        "notes": "单日重挫(-5.59%)，跌破5日线逼近10日线。短期上升结构受损，无买点。等待20日线(20.92)附近构筑双底或新平台。",
        "tags": ["第三梯队", "趋势受损", "等待企稳"],
        "conditions": [
            {"key": "ma20_break_up", "enabled": True, "params": {}},
            {"key": "rsi_oversold", "enabled": True, "params": {"threshold": 30}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
    {
        "stock_code": "002185",
        "stock_name": "华天科技",
        "buy_target_price": 14.50,  # 突破箱体
        "notes": "上涨后横盘震荡，5/10/20日均线高度粘合。方向不明，等待放量大阳线突破近期箱体顶部才符合右侧主升浪买入标准。",
        "tags": ["第三梯队", "横盘震荡", "等待方向"],
        "conditions": [
            {"key": "ma_bull_alignment", "enabled": True, "params": {}},
            {"key": "volume_surge", "enabled": True, "params": {"multiplier": 2.0}}
        ],
        "is_active": True,
        "feishu_notify": True
    },
]


def add_watchlist_items():
    print("=" * 60)
    print("批量添加买卖点监控 - 第二批")
    print("=" * 60)
    
    added_count = 0
    skipped_count = 0
    error_count = 0
    
    for item in WATCHLIST_ITEMS:
        print(f"\n处理: {item['stock_code']} - {item['stock_name']}")
        print(f"  买点: {item.get('buy_target_price', '-')}")
        print(f"  卖点: {item.get('sell_target_price', '-')}")
        print(f"  标签: {', '.join(item.get('tags', []))}")
        
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
                    error_count += 1
        except Exception as e:
            print(f"  ✗ 请求失败: {e}")
            error_count += 1
    
    print("\n" + "=" * 60)
    print(f"完成: 添加 {added_count} 只, 跳过 {skipped_count} 只, 失败 {error_count} 只")
    print("=" * 60)


if __name__ == "__main__":
    add_watchlist_items()
