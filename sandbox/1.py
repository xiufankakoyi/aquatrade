"""
ArcticDB Arrow 原生支持验证

ArcticDB 6.9.0 已经原生支持 Arrow 格式:
- 写入: lib._nvs.write(symbol, arrow_table)
- 读取: lib.read(symbol) -> 返回 pyarrow.Table (如果用 Arrow 写入)

关键发现:
- lib._nvs 是 Native Version Store，支持直接 Arrow 输入
- 写入 Arrow 后，读取自动返回 Arrow Table
- 写入 Pandas 后，读取返回 Pandas DataFrame
"""
import arcticdb as adb
import polars as pl
import pyarrow as pa


class ArcticArrowWriter:
    """
    ArcticDB Arrow 写入器
    
    ArcticDB 6.9.0 原生支持 Arrow，通过 _nvs (Native Version Store) 实现。
    """
    
    def __init__(self, arctic_lib):
        self.lib = arctic_lib
        self.nvs = arctic_lib._nvs
    
    def write_arrow(self, symbol: str, arrow_table: pa.Table, metadata: dict = None):
        """
        直接写入 Arrow Table
        
        Args:
            symbol: 数据符号
            arrow_table: PyArrow Table
            metadata: 可选元数据
            
        Returns:
            VersionedItem
        """
        return self.nvs.write(symbol, arrow_table, metadata=metadata)
    
    def read_arrow(self, symbol: str) -> pa.Table:
        """
        读取数据，返回 Arrow Table
        
        Args:
            symbol: 数据符号
            
        Returns:
            PyArrow Table (如果原始数据用 Arrow 写入)
        """
        result = self.lib.read(symbol)
        return result.data


if __name__ == "__main__":
    # 测试
    arctic = adb.Arctic('lmdb://./data/test_arrow_native')
    if 'test' not in arctic.list_libraries():
        arctic.create_library('test')
    lib = arctic['test']
    
    writer = ArcticArrowWriter(lib)
    
    # 创建测试数据
    df = pl.DataFrame({
        'date': ['2024-01-01', '2024-01-02'],
        'value': [1.0, 2.0]
    })
    arrow_table = df.to_arrow()
    
    # 写入
    result = writer.write_arrow('test_symbol', arrow_table)
    print(f"写入成功: {result}")
    
    # 读取
    data = writer.read_arrow('test_symbol')
    print(f"读取类型: {type(data)}")
    print(f"数据:\n{data}")