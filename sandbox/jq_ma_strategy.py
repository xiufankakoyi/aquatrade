
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
