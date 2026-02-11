from core.strategies.jq_volume_strategy_v2 import JQVolumeStrategypro

def test_strategy_props():
    strat = JQVolumeStrategypro()
    print(f"Strategy Name: {strat.name}")
    print(f"Max Positions: {strat.max_positions}")
    print(f"Position Ratio: {strat.position_ratio}")
    print(f"Max Stocks Per Day: {strat.max_stocks_per_day}")
    
    # Test setting
    strat.max_positions = 10
    strat.position_ratio = 0.5
    print(f"After setting:")
    print(f"Max Positions: {strat.max_positions}")
    print(f"Position Ratio: {strat.position_ratio}")
    print(f"Config Max Positions: {strat.config.max_positions}")

if __name__ == "__main__":
    test_strategy_props()
