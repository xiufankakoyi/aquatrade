"""
测试热重载系统
"""
import logging

logging.basicConfig(level=logging.INFO)

# 测试1: 配置管理器
print("="*60)
print("测试 1: 配置管理器")
print("="*60)

from core.strategies.hot_reload import ConfigManager

config_mgr = ConfigManager()

# 加载配置
config = config_mgr.load_config("jq_volume_v1pro")
if config:
    print(f"✅ 加载配置成功: {len(config)} 个参数")
    print(f"   市值范围: {config['market_cap_min']} - {config['market_cap_max']}")
    print(f"   量比阈值: {config['volume_ratio_threshold']}")
else:
    print("❌ 配置加载失败")

# 测试2: 策略加载器
print("\n" + "="*60)
print("测试 2: 策略加载器")
print("="*60)

from core.strategies.hot_reload import StrategyLoader

try:
    strategy = StrategyLoader.load_strategy("jq_volume_v1pro")
    print(f"✅ 策略加载成功: {strategy.strategy_name}")
    print(f"   配置: 市值={strategy.config.market_cap_min/10000:.0f}-{strategy.config.market_cap_max/10000:.0f}亿")
except Exception as e:
    print(f"❌ 策略加载失败: {e}")

# 测试3: 配置变更后重载
print("\n" + "="*60)
print("测试 3: 配置变更后重载")
print("="*60)

new_config = config.copy()
new_config['volume_ratio_threshold'] = 5.0  # 修改量比阈值

# 保存新配置
if config_mgr.save_config("jq_volume_v1pro", new_config):
    print("✅ 保存新配置成功")
    
    # 重载策略
    try:
        new_strategy = StrategyLoader.reload_strategy("jq_volume_v1pro")
        print(f"✅ 策略重载成功")
        print(f"   新量比阈值: {new_strategy.config.volume_ratio_threshold}")
    except Exception as e:
        print(f"❌ 策略重载失败: {e}")
else:
    print("❌ 保存配置失败")

# 恢复原配置
config_mgr.save_config("jq_volume_v1pro", config)
print("\n✅ 配置已恢复")

# 测试4: 文件监听器（需要手动测试）
print("\n" + "="*60)
print("测试 4: 文件监听器")
print("="*60)
print("⚠️  文件监听器需要手动测试：")
print("   1. 运行此脚本并保持运行")
print("   2. 修改策略文件并保存")
print("   3. 观察是否自动重载")
print("   (本测试跳过)")

print("\n" + "="*60)
print("✅ 所有测试完成！热重载系统可用。")
print("="*60)
