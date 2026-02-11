#!/usr/bin/env python3
"""
启动性能测试脚本

测试各个模块的导入时间，验证延迟加载优化效果
"""
import time
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_import_time(module_name: str, description: str):
    """测试模块导入时间"""
    print(f"\n{'='*60}")
    print(f"测试: {description}")
    print(f"模块: {module_name}")
    print('-' * 60)
    
    start = time.time()
    try:
        exec(f"import {module_name}")
        elapsed = time.time() - start
        print(f"✅ 成功 | 耗时: {elapsed:.3f}秒")
        
        # 评级
        if elapsed < 0.3:
            rating = "🟢 优秀"
        elif elapsed < 1.0:
            rating = "🟡 良好"
        elif elapsed < 3.0:
            rating = "🟠 一般"
        else:
            rating = "🔴 需优化"
        
        print(f"评级: {rating}")
        return elapsed
    except Exception as e:
        print(f"❌ 失败: {e}")
        return None


def main():
    print("\n" + "="*60)
    print("🚀 AquaTrade 启动性能测试")
    print("="*60)
    
    results = {}
    
    # 测试 1: 核心模块
    results['config'] = test_import_time('config', '配置模块')
    
    # 测试 2: 服务模块（现在应该很快）
    results['server.services'] = test_import_time('server.services', '服务模块 (已优化)')
    
    # 测试 3: 策略模块（现在应该很快）
    results['core.strategies'] = test_import_time('core.strategies', '策略模块 (已优化)')
    
    # 测试 4: 策略工厂（会触发策略扫描，但不会加载策略类）
    results['core.strategies.strategy_factory'] = test_import_time(
        'core.strategies.strategy_factory', 
        '策略工厂'
    )
    
    # 测试 5: 数据服务模块
    results['data_svc'] = test_import_time('data_svc', '数据服务模块')
    
    # 测试 6: 完整导入策略工厂并获取策略列表（会触发扫描）
    print(f"\n{'='*60}")
    print("测试: 策略工厂获取策略列表 (会触发策略扫描和加载)")
    print('-' * 60)
    start = time.time()
    try:
        from core.strategies.strategy_factory import get_factory
        factory = get_factory()
        strategies = factory.list_strategies()
        elapsed = time.time() - start
        print(f"✅ 成功 | 找到 {len(strategies)} 个策略 | 耗时: {elapsed:.3f}秒")
        results['factory_list'] = elapsed
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试 7: 数据查询类（重型模块）
    results['data_query'] = test_import_time(
        'data_svc.database.optimized_data_query',
        '数据查询类 (包含 Polars/DuckDB)'
    )
    
    # 总结
    print(f"\n\n{'='*60}")
    print("📊 性能总结")
    print('='*60)
    
    total_time = sum(t for t in results.values() if t is not None)
    print(f"\n总导入时间: {total_time:.3f}秒")
    
    print("\n优化目标达成情况:")
    goals = {
        'server.services': ('服务模块', 0.5),
        'core.strategies': ('策略模块', 0.2),
        'core.strategies.strategy_factory': ('策略工厂', 1.0),
    }
    
    for key, (name, target) in goals.items():
        if key in results and results[key] is not None:
            actual = results[key]
            status = "✅" if actual < target else "❌"
            print(f"{status} {name}: {actual:.3f}s (目标: <{target}s)")
    
    print("\n" + "="*60)
    print("🎉 测试完成！")
    print("="*60)
    
    # 详细的策略列表
    if 'factory_list' in results:
        print("\n已注册策略:")
        from core.strategies.strategy_factory import get_factory
        factory = get_factory()
        for i, strategy in enumerate(factory.list_strategies(), 1):
            print(f"  {i}. {strategy['name']} ({strategy['id']})")


if __name__ == '__main__':
    main()
