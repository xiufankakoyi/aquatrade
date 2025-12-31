# 导入框架，确保基类被加载
from . import strategy_framework

# 导入工厂
from . import strategy_factory

# 【重要】在这里显式导入你所有的策略文件
# 这会将它们加载到内存中，以便工厂可以发现它们
from . import jq_volume_strategy
from . import optimized_strategy
from . import simple_strategies
from . import trend_follow_strategy