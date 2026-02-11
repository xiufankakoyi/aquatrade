## 问题分析

1. **现象**：用户回测的是"pro"策略，但AI分析显示的却是"收敛三角形倒计时策略"。

2. **根因**：
   - 回测服务接收"pro"作为策略名称
   - 策略工厂创建策略实例时，没有将传入的策略名称传递给策略构造函数
   - 策略实例的`name`属性默认使用策略类的`strategy_name`类属性
   - 回测结果中的策略名称使用的是策略实例的`name`属性，而非传入的参数

3. **影响**：
   - AI分析基于回测结果中的策略名称进行，导致分析错误的策略
   - 用户体验不一致，看到的策略名称与实际回测的不符

## 解决方案

修改`backtest_service.py`中的`run_backtest_and_get_data`方法，确保回测结果中的策略名称与传入的策略名称一致：

1. 在`run_backtest_and_get_data`方法中，保存传入的`strategy_name`参数
2. 在调用`convert_backtest_results`方法时，使用传入的`strategy_name`参数作为策略名称，而不是`strategy.name`
3. 这样确保回测结果中的策略名称与用户请求的一致，AI分析也会使用正确的策略名称

## 修改步骤

1. 打开`d:/aquatrade/server/services/backtest_service.py`文件
2. 找到`run_backtest_and_get_data`方法
3. 修改第103行，将`strategy.name`替换为`strategy_name`
4. 保存文件

## 预期效果

- 回测结果中的`strategyInfo.name`字段将显示用户请求的策略名称（如"pro"）
- AI分析服务将基于正确的策略名称进行分析
- 用户将看到一致的策略名称，提高使用体验