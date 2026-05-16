"""
聚宽(JQData)版本的双均线策略 - 用于对比验证

这个策略与我们的回测系统使用相同的逻辑：
- 使用 MA5 和 MA10 金叉买入，死叉卖出
- T+1 执行（今日信号，明日开盘成交）
- 相同的佣金设置
"""

# 聚宽平台使用的代码（不能直接运行，需要在聚宽网站使用）
JQ_STRATEGY_CODE = '''
# 克隆自聚宽文章：https://www.joinquant.com/post/12345
# 标题：双均线策略对比验证
# 作者：Aquatrade

def initialize(context):
    """
    初始化函数，设定基准等等
    """
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    
    # 开启动态复权模式（真实价格）
    set_option('use_real_price', True)
    
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税
    set_order_cost(OrderCost(
        open_tax=0, 
        close_tax=0.001, 
        open_commission=0.0003, 
        close_commission=0.0003, 
        close_today_commission=0, 
        min_commission=5
    ), type='stock')
    
    # 运行频率
    run_daily(trade, time='09:30')  # 开盘时运行
    
    # 存储MA计算结果
    g.last_ma5 = {}
    g.last_ma10 = {}

def trade(context):
    """
    每日交易逻辑
    """
    # 获取当前日期
    current_date = context.current_dt.strftime('%Y-%m-%d')
    
    # 获取股票池：沪深300成分股
    stock_list = get_index_stocks('000300.XSHG')
    
    # 过滤：排除ST、停牌、次新股
    stock_list = filter_stocks(stock_list, current_date)
    
    # 获取历史数据计算MA
    hist = history(20, '1d', 'close', security_list=stock_list, skip_paused=True)
    
    # 计算MA5和MA10
    ma5 = hist.iloc[-5:].mean()  # 最近5天均值
    ma10 = hist.iloc[-10:].mean()  # 最近10天均值
    
    # 获取昨日MA（用于判断金叉死叉）
    ma5_prev = hist.iloc[-6:-1].mean()
    ma10_prev = hist.iloc[-11:-1].mean()
    
    # 遍历持仓，检查卖出信号
    for stock in list(context.portfolio.positions.keys()):
        if stock in ma5.index and stock in ma10.index:
            # 死叉：MA5下穿MA10
            if ma5_prev[stock] >= ma10_prev[stock] and ma5[stock] < ma10[stock]:
                order_target(stock, 0)
                log.info(f'{current_date} 卖出 {stock}')
    
    # 检查买入信号
    buy_list = []
    for stock in stock_list:
        if stock in ma5.index and stock in ma10.index:
            # 金叉：MA5上穿MA10
            if ma5_prev[stock] <= ma10_prev[stock] and ma5[stock] > ma10[stock]:
                buy_list.append(stock)
    
    # 限制持仓数量
    hold_count = len(context.portfolio.positions)
    max_hold = 5
    
    if hold_count < max_hold and buy_list:
        # 每只股票的仓位
        cash_per_stock = context.portfolio.available_cash / (max_hold - hold_count)
        
        for stock in buy_list[:max_hold - hold_count]:
            # 下单
            order_value(stock, cash_per_stock)
            log.info(f'{current_date} 买入 {stock}')

def filter_stocks(stock_list, current_date):
    """
    过滤股票：排除ST、停牌、次新股
    """
    # 获取基本信息
    curr_data = get_current_data()
    
    filtered = []
    for stock in stock_list:
        # 排除停牌
        if curr_data[stock].paused:
            continue
        
        # 排除ST
        if curr_data[stock].is_st:
            continue
        
        # 排除次新股（上市不足60天）
        days_listed = (datetime.strptime(current_date, '%Y-%m-%d') - 
                      curr_data[stock].day).days
        if days_listed < 60:
            continue
        
        filtered.append(stock)
    
    return filtered
'''

# 对比说明
COMPARISON_DOC = """
================================================================================
聚宽策略与 Aquatrade 回测系统对比说明
================================================================================

1. 策略逻辑对比
--------------------------------------------------------------------------------

| 项目           | 聚宽策略                          | Aquatrade 回测系统           |
|----------------|-----------------------------------|------------------------------|
| 买入信号       | MA5上穿MA10（金叉）               | MA5上穿MA10（金叉）          |
| 卖出信号       | MA5下穿MA10（死叉）               | MA5下穿MA10（死叉）          |
| 执行价格       | 开盘价（set_option真实价格）      | 开盘价                       |
| 执行时间       | T+1（信号产生后次日开盘）         | T+1（信号产生后次日开盘）    |
| 股票池         | 沪深300成分股                     | 全市场（可配置）             |
| 过滤条件       | 排除ST、停牌、次新股              | 可配置                       |
| 佣金           | 买入0.03%，卖出0.03%+0.1%印花税   | 可配置（默认0.03%）          |
| 仓位管理       | 均分资金                          | 均分资金                     |

2. 数据对比要点
--------------------------------------------------------------------------------

- 价格数据：聚宽使用复权价格，Aquatrade 使用复权价格
- 市值单位：聚宽使用"元"，需要确认 Aquatrade 的单位
- 停牌处理：聚宽 skip_paused=True，Aquatrade 使用 is_suspended 标记
- 涨跌停：聚宽自动处理，Aquatrade 使用 is_limit_up/down 标记

3. 验证方法
--------------------------------------------------------------------------------

(1) 相同时间段回测对比（如 2023-01-01 到 2023-12-31）
(2) 对比指标：
    - 总收益率
    - 年化收益率
    - 最大回撤
    - 夏普比率
    - 交易次数
    - 胜率

(3) 如果结果差异较大，检查：
    - 数据起始时间是否一致
    - 复权方式是否一致（前复权/后复权）
    - 股票池是否一致
    - 交易费用设置是否一致
    - 停牌、涨跌停处理是否一致

4. 预期差异
--------------------------------------------------------------------------------

由于以下原因，两个系统的结果可能略有差异：
- 数据源不同（聚宽 vs 本地数据库）
- 股票池构建方式不同
- 复权算法可能略有差异
- 停牌、涨跌停的标记时机可能不同

如果差异在 1-2% 以内，通常认为是正常的。
如果差异超过 5%，需要仔细检查数据准确性。

================================================================================
"""


def print_strategy_code():
    """打印聚宽策略代码"""
    print(JQ_STRATEGY_CODE)
    
    # 保存到文件
    with open('c:\\Users\\Liu\\Desktop\\projects\\aquatrade\\sandbox\\jq_ma_strategy.py', 'w', encoding='utf-8') as f:
        f.write(JQ_STRATEGY_CODE)
    
    print("\n✅ 策略代码已保存到: sandbox/jq_ma_strategy.py")


def print_comparison_doc():
    """打印对比说明"""
    print(COMPARISON_DOC)


if __name__ == "__main__":
    print_comparison_doc()
    print("\n" + "=" * 80)
    print("聚宽策略代码")
    print("=" * 80)
    print_strategy_code()
