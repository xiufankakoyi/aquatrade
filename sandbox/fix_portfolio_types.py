"""
修复 ArcticDB 中的持仓数据类型
"""
from arcticdb import Arctic
import pandas as pd

arctic = Arctic("lmdb://C:/Users/Liu/Desktop/projects/aquatrade/data/arctic_db")

# 检查 portfolio 库
if 'portfolio' in arctic.list_libraries():
    lib = arctic['portfolio']
    
    if 'positions' in lib.list_symbols():
        print("读取现有数据...")
        data = lib.read('positions')
        df = data.data
        
        print(f"\n当前数据类型:")
        print(df.dtypes)
        
        print(f"\n数据内容:")
        print(df)
        
        # 修复数据类型
        print("\n修复数据类型...")
        
        # 遍历所有列，转换为 ArcticDB 支持的类型
        for col in df.columns:
            dtype = str(df[col].dtype)
            
            # 处理可空整数类型 (Int32, Int64 等)
            if dtype.startswith('Int') or dtype.startswith('UInt'):
                print(f"  {col}: {dtype} -> int64/float64")
                if col == 'id':
                    df[col] = df[col].astype('int64')
                elif col in ['shares', 'cost', 'buy_price', 'stop_loss', 'take_profit']:
                    df[col] = df[col].astype('float64')
                else:
                    df[col] = df[col].astype('int64')
            
            # 处理可空浮点类型
            elif dtype.startswith('Float'):
                print(f"  {col}: {dtype} -> float64")
                df[col] = df[col].astype('float64')
            
            # 处理布尔类型
            elif dtype == 'bool':
                print(f"  {col}: {dtype} -> int64")
                df[col] = df[col].astype('int64')
        
        print(f"\n修复后的数据类型:")
        print(df.dtypes)
        
        # 重新写入
        print("\n重新写入 ArcticDB...")
        lib.write('positions', df)
        print("完成!")
        
        # 验证
        print("\n验证读取...")
        data2 = lib.read('positions')
        df2 = data2.data
        print(df2.dtypes)
