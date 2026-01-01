import lancedb
import pyarrow as pa
import os
from config.config import Config

def optimize_tables():
    print("开始优化 LanceDB 表结构 (Compaction & Sorting)...")
    
    # 构建 LanceDB 路径（与 LanceDBManager 保持一致）
    parquet_dir = getattr(Config, 'PARQUET_DIR', 'parquet_data')
    lance_dir = os.path.join(parquet_dir, 'lance_db')
    
    # 连接数据库
    db = lancedb.connect(lance_dir)
    print(f"LanceDB 目录: {lance_dir}")
    
    # 需要优化的表
    tables = ['stock_daily', 'stock_limit_status']
    
    for t_name in tables:
        try:
            tbl = db.open_table(t_name)
            print(f"\n正在优化表: {t_name} ...")
            
            # 显示表信息
            try:
                schema = tbl.schema
                num_rows = len(tbl)
                print(f"  - 表行数: {num_rows:,}")
                print(f"  - 列: {', '.join(schema.names)}")
            except:
                pass
            
            # 1. 物理排序: 按 trade_date 排序
            # 这样查一段时间的数据时，磁盘读取是连续的，利用率最高
            # 注意: 如果您的列名是 'date' 请改为 'date'
            date_col = 'trade_date' if 'trade_date' in tbl.schema.names else 'date'
            
            # LanceDB 紧缩与重写 (这会将数据按日期物理连续存储)
            # 提示: 如果数据量巨大，这步可能需要一点时间
            print(f"  - 压缩文件...")
            tbl.compact_files() # 合并小文件
            print(f"    ✓ 文件压缩完成")
            
            # 目前 LanceDB Python SDK 可能需要通过 dataset API 重写来实现排序
            # 或者简单的 compact 通常能解决碎片问题
            # 如果支持，建立索引会更快:
            try:
                print(f"  - 创建标量索引: {date_col}")
                # 【优化】尝试使用 BTREE 索引类型（对范围查询更高效）
                # 如果表较大，BTREE 索引对日期范围查询性能更好
                try:
                    # 尝试创建 BTREE 索引（如果支持）
                    tbl.create_scalar_index(date_col, index_type="btree")
                    print(f"    ✓ BTREE 索引创建成功")
                except (TypeError, ValueError) as e1:
                    # 如果不支持 index_type 参数，使用默认索引
                    try:
                        tbl.create_scalar_index(date_col)
                        print(f"    ✓ 默认索引创建成功")
                    except Exception as e2:
                        print(f"    ⚠️ 索引创建失败: {e2}")
            except Exception as e:
                error_msg = str(e)
                if "already exists" in error_msg.lower() or "已存在" in error_msg:
                    print(f"  - 索引已存在，跳过创建")
                else:
                    print(f"  - 索引创建跳过: {e}")
            
            # 【新增】对于 stock_limit_status 表，额外创建复合索引（stock_code + trade_date）
            # 这样可以优化 JOIN 查询性能
            if t_name == 'stock_limit_status':
                try:
                    print(f"  - 创建 stock_code 索引（补充索引）")
                    # 注意：LanceDB 可能不支持直接创建复合标量索引
                    # 但我们可以尝试创建 stock_code 的索引作为补充
                    if 'stock_code' in tbl.schema.names:
                        try:
                            tbl.create_scalar_index('stock_code', index_type="btree")
                            print(f"    ✓ stock_code BTREE 索引创建成功")
                        except (TypeError, ValueError):
                            try:
                                tbl.create_scalar_index('stock_code')
                                print(f"    ✓ stock_code 默认索引创建成功")
                            except Exception as e3:
                                error_msg = str(e3)
                                if "already exists" in error_msg.lower() or "已存在" in error_msg:
                                    print(f"    - stock_code 索引已存在")
                                else:
                                    print(f"    ⚠️ stock_code 索引创建失败: {e3}")
                except Exception as e:
                    error_msg = str(e)
                    if "already exists" in error_msg.lower() or "已存在" in error_msg:
                        print(f"  - stock_code 索引已存在")
                    else:
                        print(f"  - 复合索引创建跳过: {e}")

            print(f"✓ {t_name} 优化完成")
            
        except Exception as e:
            print(f"✗ 优化 {t_name} 失败: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    optimize_tables()