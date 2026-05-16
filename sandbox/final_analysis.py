"""
最终收益对比分析
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

print("=" * 70)
print("最终收益对比分析")
print("=" * 70)

# AquaTrade 结果
aqua_return = 6.07
aqua_final = 106073.27

# 聚宽结果
jq_return = 5.24

# 差异
diff = aqua_return - jq_return
diff_pct = abs(diff) / jq_return * 100

print(f"\n【收益对比】")
print(f"  AquaTrade: {aqua_return:.2f}%")
print(f"  聚宽: {jq_return:.2f}%")
print(f"  差异: {diff:.2f}% ({diff_pct:.1f}%)")

print(f"\n【差异原因分析】")
print(f"  1. 交易信号不同：")
print(f"     - AquaTrade 在 2025-03-10 买入，2025-03-20 卖出（亏损）")
print(f"     - AquaTrade 在 2025-06-23 买入，2025-07-18 卖出（盈利）")
print(f"     - 聚宽跳过了这些交易")
print(f"  ")
print(f"  2. 分红处理：")
print(f"     - 2025-06-12 发放现金分红 2844.01 元")
print(f"     - AquaTrade 正确处理了分红")

print(f"\n【结论】")
if abs(diff) < 0.5:
    print(f"  ✓ 收益差异 {abs(diff):.2f}% < 0.5%，在容差范围内")
else:
    print(f"  ✗ 收益差异 {abs(diff):.2f}% >= 0.5%，超出容差范围")
    print(f"  ")
    print(f"  主要原因：")
    print(f"    - 数据源差异导致MA计算结果不同")
    print(f"    - 聚宽可能使用了额外的信号过滤逻辑")
    print(f"    - 需要确认聚宽使用的具体数据源和MA计算方式")

print(f"\n【建议】")
print(f"  1. 确认聚宽使用的数据源（Tushare/其他）")
print(f"  2. 确认聚宽的MA计算方式（简单移动平均/指数移动平均）")
print(f"  3. 确认聚宽是否有额外的信号过滤条件")
print(f"  4. 如果数据源不同，则差异是正常的")
