"""
聚宽（JoinQuant）平台 MA 金叉死叉策略
与 AquaTrade 策略逻辑完全一致，用于对比验证

策略逻辑：
- 股票: 000001.XSHE (平安银行)
- 买入条件: MA5 上穿 MA10 (金叉)
- 卖出条件: MA5 下穿 MA10 (死叉)
- 回测区间: 2025-01-01 到 2026-01-01
"""

# 聚宽初始化函数
from jqdata import *


def initialize(context):
    """
    初始化函数，设定基准等等
    """
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    
    # 股票池：只交易平安银行
    g.security = '000001.XSHE'
    
    # 记录信号日志
    g.signal_log = []
    
    # 打印策略信息
    log.info('========================================')
    log.info('MA金叉死叉策略 - 聚宽版本')
    log.info('目标股票: 000001.XSHE (平安银行)')
    log.info('买入条件: MA5 上穿 MA10 (金叉)')
    log.info('卖出条件: MA5 下穿 MA10 (死叉)')
    log.info('========================================')
    
    # 运行频率：每天开盘前运行
    run_daily(before_market_open, time='09:00')
    
    # 运行频率：每天交易时运行
    run_daily(market_open, time='09:30')
    
    # 运行频率：每天收盘后运行
    run_daily(after_market_close, time='15:30')


def before_market_open(context):
    """
    开盘前运行函数
    """
    # 获取当前日期
    current_date = context.current_dt.strftime('%Y-%m-%d')
    log.info(f'[{current_date}] 开盘前准备')


def market_open(context):
    """
    交易函数，每个交易日开盘时运行
    核心策略逻辑
    """
    security = g.security
    current_date = context.current_dt.strftime('%Y-%m-%d')
    
    # 获取历史价格数据
    # 获取最近20天的收盘价，用于计算MA5和MA10
    close_data = attribute_history(security, 20, '1d', ['close'], skip_paused=True)
    
    if len(close_data) < 10:
        log.info(f'[{current_date}] 历史数据不足，跳过')
        return
    
    # 计算MA5和MA10
    # MA5: 最近5天收盘价的平均值
    # MA10: 最近10天收盘价的平均值
    ma5 = close_data['close'][-5:].mean()
    ma10 = close_data['close'][-10:].mean()
    
    # 获取昨天的MA5和MA10（用于判断交叉）
    if len(close_data) >= 11:
        ma5_yesterday = close_data['close'][-6:-1].mean()
        ma10_yesterday = close_data['close'][-11:-1].mean()
    else:
        log.info(f'[{current_date}] 数据不足以计算昨日均线，跳过')
        return
    
    # 获取当前价格
    current_price = close_data['close'][-1]
    
    # 打印当前状态
    log.info(f'[{current_date}] 价格: {current_price:.2f}, MA5: {ma5:.2f}, MA10: {ma10:.2f}')
    log.info(f'[{current_date}] 昨日MA5: {ma5_yesterday:.2f}, 昨日MA10: {ma10_yesterday:.2f}')
    
    # 获取当前持仓
    holding = context.portfolio.positions[security].total_amount if security in context.portfolio.positions else 0
    
    # ==================== 金叉判断 ====================
    # 金叉条件: 昨天MA5 < MA10，今天MA5 > MA10
    if ma5_yesterday < ma10_yesterday and ma5 > ma10:
        log.info(f'>>> [{current_date}] 金叉信号! MA5({ma5:.2f}) 上穿 MA10({ma10:.2f})')
        
        # 记录信号
        g.signal_log.append({
            'date': current_date,
            'type': '金叉',
            'price': current_price,
            'ma5': ma5,
            'ma10': ma10
        })
        
        # 如果没有持仓，买入
        if holding == 0:
            # 计算可买入数量（使用全部可用资金的90%）
            cash = context.portfolio.available_cash * 0.9
            order_value(security, cash)
            log.info(f'>>> [{current_date}] 买入 {security}，金额: {cash:.2f}')
        else:
            log.info(f'[{current_date}] 已持仓，不重复买入')
    
    # ==================== 死叉判断 ====================
    # 死叉条件: 昨天MA5 > MA10，今天MA5 < MA10
    elif ma5_yesterday > ma10_yesterday and ma5 < ma10:
        log.info(f'>>> [{current_date}] 死叉信号! MA5({ma5:.2f}) 下穿 MA10({ma10:.2f})')
        
        # 记录信号
        g.signal_log.append({
            'date': current_date,
            'type': '死叉',
            'price': current_price,
            'ma5': ma5,
            'ma10': ma10
        }])
        
        # 如果有持仓，卖出
        if holding > 0:
            order_target(security, 0)
            log.info(f'>>> [{current_date}] 卖出 {security}，数量: {holding}')
        else:
            log.info(f'[{current_date}] 无持仓，不卖出')
    else:
        log.info(f'[{current_date}] 无交叉信号')


def after_market_close(context):
    """
    收盘后运行函数
    """
    current_date = context.current_dt.strftime('%Y-%m-%d')
    
    # 获取当前持仓和总资产
    holding = context.portfolio.positions[g.security].total_amount if g.security in context.portfolio.positions else 0
    total_value = context.portfolio.total_value
    
    log.info(f'[{current_date}] 收盘后统计:')
    log.info(f'  持仓数量: {holding}')
    log.info(f'  总资产: {total_value:.2f}')
    
    # 记录交易日志
    trades = get_trades()
    for trade in trades.values():
        if trade.security == g.security:
            action = '买入' if trade.action == 'buy' else '卖出'
            log.info(f'  今日交易: {action} {trade.security} 价格:{trade.price:.2f} 数量:{trade.amount}')


# ==================== 回测配置 ====================
"""
在聚宽平台上，你需要在回测设置中配置以下参数：

1. 回测时间：
   - 开始日期：2025-01-01
   - 结束日期：2026-01-01

2. 资金设置：
   - 初始资金：100000 (10万元)
   - 回测频率：每天

3. 基准对比：
   - 基准指数：沪深300 (000300.XSHG)

4. 交易费用：
   - 佣金：万分之三 (0.0003)
   - 印花税：千分之一 (卖出时收取，0.001)
   - 最低佣金：5元
"""
