"""测试接口初始化"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    print("初始化三层架构接口...")
    from data_svc.unified_data_interface import get_unified_data_interface
    interface = get_unified_data_interface()
    
    if interface:
        print("✅ 接口初始化成功")
        print(f"  - storage: {type(interface.storage)}")
        print(f"  - bridge: {type(interface.bridge)}")
        print(f"  - analytics: {type(interface.analytics)}")
    else:
        print("❌ 接口初始化失败，返回 None")
        
except Exception as e:
    print(f"❌ 初始化错误: {e}")
    import traceback
    traceback.print_exc()
