import time
import sys
import json
from pathlib import Path

# 添加项目根目录到路径
_project_root = Path(__file__).parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from data_svc.lance_manager import LanceDBManager

def test_load_speed():
    print("=" * 60)
    print("性能测试：LanceDB 数据加载速度")
    print("=" * 60)
    
    # 清空之前的日志
    log_file = Path(_project_root) / '.cursor' / 'debug.log'
    try:
        if log_file.exists():
            log_file.write_text('', encoding='utf-8')
    except:
        pass
    
    manager = LanceDBManager()
    start_t = time.time()
    
    # 模拟回测请求：加载一个月的数据
    print("\n[1/4] 开始加载数据...")
    print("  日期范围: 2024-01-01 ~ 2024-02-01")
    print("  列: trade_date, open, close, high, low, volume")
    
    init_time = time.time() - start_t
    print(f"  初始化耗时: {init_time:.3f}s")
    
    load_start = time.time()
    df = manager.load_to_polars(
        start_date="2024-01-01", 
        end_date="2024-02-01", 
        columns=["trade_date", "open", "close", "high", "low", "volume"]
    )
    load_cost = time.time() - load_start
    
    total_cost = time.time() - start_t
    
    print(f"\n[2/4] 数据加载完成")
    print(f"  行数: {len(df):,}")
    print(f"  列数: {len(df.columns)}")
    print(f"  加载耗时: {load_cost:.3f}s")
    print(f"  总耗时: {total_cost:.3f}s")
    
    # 检查数据
    if len(df) > 0:
        print(f"\n[3/4] 数据样本:")
        print(df.head(3))
        print(f"\n数据日期范围: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
    else:
        print("\n[警告] 未加载到任何数据！")
    
    # 分析性能日志
    print(f"\n[4/4] 性能分析:")
    try:
        if log_file.exists():
            logs = []
            for line in log_file.read_text(encoding='utf-8').strip().split('\n'):
                if line.strip():
                    try:
                        logs.append(json.loads(line))
                    except:
                        pass
            
            # 查找性能相关的日志
            query_logs = [log for log in logs if 'lance_manager.py' in log.get('location', '')]
            if query_logs:
                print(f"  找到 {len(query_logs)} 条性能日志")
                for log in query_logs[-5:]:  # 显示最后5条
                    msg = log.get('message', '')
                    data = log.get('data', {})
                    if 'elapsed' in data:
                        print(f"    {msg}: {data.get('elapsed', 0):.3f}s")
                    elif 'rows' in data:
                        print(f"    {msg}: {data.get('rows', 0):,} 行")
            else:
                print("  未找到性能日志")
    except Exception as e:
        print(f"  分析日志失败: {e}")
    
    print("\n" + "=" * 60)
    if load_cost > 1.0:
        print("[WARNING] 性能警告: 加载耗时超过 1 秒，需要优化！")
        print("  建议：检查 debug.log 中的详细性能日志")
        return False
    else:
        print("[OK] 性能正常: 加载耗时在 1 秒以内")
        return True

if __name__ == "__main__":
    success = test_load_speed()
    sys.exit(0 if success else 1)

