from core.strategies.templates.ai_base import AIStrategyBase, AIStrategyConfig

class AIGeneratedStrategy(AIStrategyBase) 的代码模板，但类名必须是 AIGeneratedStrategy，strategy_name 设置为 "均线策略"。

根据用户需求，生成代码。
</think>
```python
from core.strategies.templates.ai_base import AIStrategyBase, AIStrategyConfig

class AIGeneratedStrategy(AIStrategyBase):
    strategy_name = "均线策略"

    def __init__(self, config: AIStrategyConfig = None):
        # 如果未提供 config，使用默认参数
        if config is None:
            config = AIStrategyConfig(params={{
                "ma_fast_period": 12,
                "ma_slow_period": 20,
                "ma_period": 20,
                "fast_ema_period": 12,
                "slow_ema_period": 20,
                "signal_column": "dif",
                "max_holding_days": 5,
                "max_holding_days": 5,
                "max_holding_days": 5,
                "stop_loss_pct": -10,
                "take_profit_pct": 0.1,
                "stop_loss_pct": -10,
                "max_profit_pct": 20,
                "max_holding_days": 5,
                "max_holding_days": 5,
                "max_holding_days": 5,
                "max_holding_days": 5,
                "max_holding_days": 5,
                "max_holding_days": 5,
                "holding_state": {holding_days": 0, "buy_price": 0.0}
            }})

    def get_required_indicators(self):
        return [
            {"name": "MA", "period": self.config.params.get("ma_period", 20), "column": "close"},
            {"name": "MA", "period": self.config.params.get("ma_period", 20), "column": "close"}
        ]

    def _generate_signals_impl(self, current_date, stock_pool):
        # 从 config 获取参数
        ma_period = self.config.params.get("ma_period", 20)
        fast_period = self.config.params.get("fast", 12)
        slow_period = self.config.params.get("slow", 26)
        signal_period = self.config.params.get("signal_period", 9)
        volume_threshold = self.config.params.get("volume_buy_threshold", 1000000)
        volume_ma_period = self.config.params.get("volume_ma_period", 5) or 5)
        # 卖出逻辑：检查均线突破条件
        for code in self.signals_dict.keys() or row.get("volume") or row.get("holding_days") > 0: 
            # 注意：在 _generate_signals_impl 中，只能使用 self.holding_state[code] 中记录的指标参数
        name = self.config.params.get("ma_period", 20)
        # 注意：列名可能为