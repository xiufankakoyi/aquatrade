"""
测试改进 OCR 识别和解析
"""
import re

# 模拟 OCR 结果（从截图看实际格式）
test_text = """东方锆业
买14:50:19
15.510
200
3102.000
东方锆业
买14:50:19
15.510
300
4653.000
东方锆业
买14:50:19
15.510
500
7755.000
东方锆业
买14:50:19
15.510
500
7755.000
东方锆业
买14:50:19
15.510
100
1551.000
中航西飞
买14:27:33
31.100
200
6220.000
中航西飞
买14:27:33
31.100
600
18660.000
通富微电
买11:20:15
51.100
200
10220.000
桐昆股份
卖11:06:26
24.370
100
2437.000
桐昆股份
卖11:06:24
24.370
1200
29244.000
招商轮船
卖11:04:05
16.820
100
1682.000
招商轮船
卖11:04:05
16.840
500
8420.000
通富微电
买11:00:06
51.460
500
25730.000
新洁能
卖10:43:02
47.260
300
14178.000
新洁能
卖10:43:02
47.260
200
9452.000
雪迪龙
买10:13:46
11.160
100
1116.000
雪迪龙
买10:13:46
11.160
2100
23436.000
洁美科技
卖10:01:08
43.220
400
17288.000
黄河旋风
买09:25:00
9.300
231
2148.300
黄河旋风
买09:25:00
9.300
500
4650.000
黄河旋风
买09:25:00
9.300
269
2501.700"""


def parse_trades_v2(text):
    """
    改进的交易记录解析
    根据实际 OCR 格式：股票名 + 买/卖 + 时间 + 价格 + 数量 + 金额
    """
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    trades = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 识别股票名称（2-4个汉字）
        if re.match(r'^[\u4e00-\u9fa5]{2,4}$', line):
            stock_name = line
            
            # 检查下一条是否是买卖标记+时间
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                
                # 匹配 "买14:50:19" 或 "卖11:06:26"
                time_match = re.match(r'^(买|卖)(\d{2}:\d{2}:\d{2})$', next_line)
                
                if time_match:
                    direction = '买入' if time_match.group(1) == '买' else '卖出'
                    trade_time = time_match.group(2)
                    
                    # 后续应该是：价格、数量、金额
                    if i + 4 < len(lines):
                        price = lines[i + 2]
                        quantity = lines[i + 3]
                        amount = lines[i + 4]
                        
                        # 验证格式
                        if (re.match(r'^\d+\.\d+$', price) and 
                            re.match(r'^\d+$', quantity) and
                            re.match(r'^\d+\.\d+$', amount)):
                            
                            trades.append({
                                'stock_name': stock_name,
                                'trade_time': trade_time,
                                'quantity': quantity,
                                'amount': amount,
                                'direction': direction,
                                'price': price,
                            })
                            i += 5
                            continue
        
        i += 1
    
    return trades


def format_output(trades):
    """格式化输出"""
    if not trades:
        return "未识别到交易记录"
    
    lines = ["📊 交易记录解析结果\n"]
    lines.append(f"{'股票名称':<8} {'成交时间':<10} {'成交数量':>8} {'成交额':>12} {'成交方向':<6}")
    lines.append("-" * 55)
    
    for trade in trades:
        lines.append(
            f"{trade['stock_name']:<8} {trade['trade_time']:<10} {trade['quantity']:>8} {trade['amount']:>12} {trade['direction']:<6}"
        )
    
    lines.append(f"\n共 {len(trades)} 条交易记录")
    return "\n".join(lines)


if __name__ == "__main__":
    trades = parse_trades_v2(test_text)
    print(format_output(trades))
