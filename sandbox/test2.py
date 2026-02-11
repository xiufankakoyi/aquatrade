import sys
from pathlib import Path
import time

# 路径黑魔法
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_svc.lance_manager import LanceDBManager

def verify_data():
    print("="*40)
    print("🚀 终极数据验证 (基于真实样本)")
    print("="*40)

    mgr = LanceDBManager(table_name="stock_min_1m")

    # 使用刚才 peek 到的真实数据条件
    target_code = "000001" 
    # 注意：根据你的日志，数据在 2020-10-09 上午
    start_time = "2020-10-09 09:31:00"
    end_time   = "2020-10-09 10:00:00"
    
    print(f"\n[1] 尝试读取 {target_code}")
    print(f"    时间范围: {start_time} -> {end_time}")
    
    t0 = time.time()
    try:
        # 这一步会调用我们修复过的 load_to_polars_lazy (自动识别 trade_time)
        df = mgr.load_to_polars(
            stock_codes=[target_code],
            start_date=start_time,
            end_date=end_time,
            columns=['stock_code', 'trade_time', 'close', 'volume']
        )
        
        cost = time.time() - t0
        print(f"\n✅ 读取成功！耗时: {cost:.4f}秒")
        print(f"✅ 数据行数: {len(df)}")
        print(f"✅ 数据预览:")
        print(df)
        
        if len(df) > 0:
            print("\n🎉 恭喜！数据层建设完毕。")
            print("   现在你可以开始编写回测策略了！")
        else:
            print("\n⚠️ 警告：读取结果为空（理论上不该发生，请检查日期范围）。")

    except Exception as e:
        print(f"\n❌ 读取失败: {e}")

if __name__ == "__main__":
    verify_data()