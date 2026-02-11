"""
CSV vs Parquet 数据一致性验证脚本
使用 Polars 快速验证 date 文件夹中的 CSV 数据与 Parquet 文件中的数据是否一致
"""

import polars as pl
from pathlib import Path
from typing import Dict, List, Tuple
import sys
from datetime import datetime


# 列名映射：CSV中文列名 -> Parquet英文列名
COLUMN_MAPPING = {
    "股票代码": "stock_code",
    "TS代码": "ts_code",
    "交易日期": "trade_date",
    "开盘价": "open",
    "最高价": "high",
    "最低价": "low",
    "收盘价": "close",
    "前收盘价": "prev_close",
    "涨跌额": "change_amount",
    "涨跌幅(%)": "change_pct",
    "成交量(手)": "volume",
    "成交额(千元)": "amount",
    "换手率(%)": "turnover_rate",
    "换手率(自由流通股)": "turnover_free",
    "量比": "volume_ratio",
    "市盈率": "pe",
    "市盈率(TTM,亏损的PE为空)": "pe_ttm",
    "市净率": "pb",
    "市销率": "ps",
    "市销率(TTM)": "ps_ttm",
    "股息率(%)": "dividend_yield",
    "股息率(TTM)(%)": "dividend_yield_ttm",
    "总股本(万股)": "total_shares",
    "流通股本(万股)": "float_shares",
    "自由流通股本(万股)": "free_float_shares",
    "总市值(万元)": "total_mv",
    "流通市值(万元)": "float_mv",
    "今日涨停价": "limit_up",
    "今日跌停价": "limit_down",
    "复权因子": "adj_factor",
}


class CSVParquetVerifier:
    """CSV 和 Parquet 数据一致性验证器"""
    
    def __init__(self, csv_dir: str, parquet_file: str):
        self.csv_dir = Path(csv_dir)
        self.parquet_file = Path(parquet_file)
        self.errors = []
        self.warnings = []
        self.stats = {
            "total_files": 0,
            "matched_files": 0,
            "mismatched_files": 0,
            "skipped_files": 0,
            "total_rows_csv": 0,
            "total_rows_parquet": 0,
        }
        
    def log_error(self, msg: str):
        """记录错误"""
        self.errors.append(msg)
        print(f"❌ {msg}")
        
    def log_warning(self, msg: str):
        """记录警告"""
        self.warnings.append(msg)
        print(f"⚠️  {msg}")
        
    def log_info(self, msg: str):
        """记录信息"""
        print(f"ℹ️  {msg}")
        
    def log_success(self, msg: str):
        """记录成功"""
        print(f"✅ {msg}")
        
    def get_csv_files(self) -> List[Path]:
        """获取所有 CSV 文件"""
        csv_files = sorted(self.csv_dir.glob("*.csv"))
        self.log_info(f"找到 {len(csv_files)} 个 CSV 文件")
        return csv_files
    
    def read_csv_file(self, csv_path: Path) -> pl.DataFrame:
        """读取单个 CSV 文件"""
        try:
            df = pl.read_csv(
                csv_path,
                encoding="utf-8",
                infer_schema_length=10000,
                null_values=["", "NA", "NULL", "null"]
            )
            return df
        except Exception as e:
            self.log_error(f"读取 CSV 文件失败 {csv_path.name}: {e}")
            return None
    
    def read_parquet_file(self) -> pl.DataFrame:
        """读取 Parquet 文件"""
        try:
            df = pl.read_parquet(self.parquet_file)
            self.log_info(f"Parquet 文件包含 {len(df):,} 行数据")
            return df
        except Exception as e:
            self.log_error(f"读取 Parquet 文件失败: {e}")
            return None
    
    def extract_stock_code(self, filename: str) -> str:
        """从文件名提取股票代码"""
        return filename.replace(".csv", "")
    
    def map_csv_columns(self, csv_df: pl.DataFrame) -> pl.DataFrame:
        """将 CSV 的中文列名映射为英文列名"""
        rename_dict = {}
        for csv_col in csv_df.columns:
            if csv_col in COLUMN_MAPPING:
                rename_dict[csv_col] = COLUMN_MAPPING[csv_col]
        
        if rename_dict:
            csv_df = csv_df.rename(rename_dict)
        
        return csv_df
    
    def compare_dataframes(
        self, 
        csv_df: pl.DataFrame, 
        parquet_df: pl.DataFrame, 
        stock_code: str
    ) -> Dict[str, any]:
        """比较两个 DataFrame 的数据一致性"""
        result = {
            "stock_code": stock_code,
            "csv_rows": len(csv_df),
            "parquet_rows": len(parquet_df),
            "row_count_match": False,
            "data_match": False,
            "mismatches": []
        }
        
        # 1. 比较行数
        if len(csv_df) != len(parquet_df):
            result["mismatches"].append(
                f"行数不匹配: CSV={len(csv_df):,}, Parquet={len(parquet_df):,}"
            )
        else:
            result["row_count_match"] = True
        
        # 2. 找出共同的核心列（用于数据比较）
        core_columns = ["trade_date", "open", "high", "low", "close", "volume"]
        available_cols = [col for col in core_columns if col in csv_df.columns and col in parquet_df.columns]
        
        if not available_cols:
            result["mismatches"].append("没有找到可比较的核心列")
            return result
        
        # 3. 比较核心数据
        if result["row_count_match"] and len(csv_df) > 0:
            try:
                # 按交易日期排序
                csv_sorted = csv_df.select(available_cols).sort("trade_date")
                parquet_sorted = parquet_df.select(available_cols).sort("trade_date")
                
                # 比较数据
                # 对于浮点数，使用近似比较（容忍小的精度差异）
                matches = True
                for col in available_cols:
                    if col == "trade_date":
                        # 日期列精确比较
                        if not csv_sorted[col].equals(parquet_sorted[col]):
                            matches = False
                            result["mismatches"].append(f"列 '{col}' 数据不匹配")
                    else:
                        # 数值列使用相对误差比较（容忍 0.01% 的误差）
                        csv_col = csv_sorted[col].cast(pl.Float64)
                        parquet_col = parquet_sorted[col].cast(pl.Float64)
                        
                        # 计算相对误差
                        diff = (csv_col - parquet_col).abs()
                        rel_error = (diff / (parquet_col.abs() + 1e-10)).max()
                        
                        if rel_error > 0.0001:  # 0.01% 容忍度
                            matches = False
                            result["mismatches"].append(
                                f"列 '{col}' 数据不匹配 (最大相对误差: {rel_error:.6f})"
                            )
                
                result["data_match"] = matches
                
            except Exception as e:
                result["mismatches"].append(f"数据比较失败: {e}")
        
        return result
    
    def verify_single_stock(self, csv_path: Path, parquet_df: pl.DataFrame) -> Dict:
        """验证单个股票的数据"""
        stock_code = self.extract_stock_code(csv_path.name)
        
        # 读取 CSV
        csv_df = self.read_csv_file(csv_path)
        if csv_df is None:
            return None
        
        # 映射列名
        csv_df = self.map_csv_columns(csv_df)
        
        # 从 Parquet 中筛选对应股票的数据
        # Parquet 中的 stock_code 就是纯数字代码（如 "000001", "600000"）
        # 需要确保 stock_code 是字符串类型并保留前导零
        parquet_stock_df = parquet_df.filter(
            pl.col("stock_code") == stock_code
        )
        
        if len(parquet_stock_df) == 0:
            self.log_warning(f"Parquet 中未找到股票 {stock_code} 的数据")
            return None
        
        # 更新统计
        self.stats["total_rows_csv"] += len(csv_df)
        self.stats["total_rows_parquet"] += len(parquet_stock_df)
        
        # 比较数据
        return self.compare_dataframes(csv_df, parquet_stock_df, stock_code)
    
    def verify_all(self, sample_size: int = None, fast_mode: bool = False) -> Dict:
        """验证所有数据
        
        Args:
            sample_size: 采样数量，None 表示验证所有文件
            fast_mode: 快速模式，只验证行数，不比较具体数据
        """
        print("\n" + "="*80)
        print("CSV vs Parquet 数据一致性验证")
        print("="*80 + "\n")
        
        start_time = datetime.now()
        
        # 读取 Parquet 文件
        self.log_info("正在读取 Parquet 文件...")
        parquet_df = self.read_parquet_file()
        if parquet_df is None:
            return {"success": False, "error": "无法读取 Parquet 文件"}
        
        # 获取 CSV 文件列表
        csv_files = self.get_csv_files()
        if not csv_files:
            return {"success": False, "error": "未找到 CSV 文件"}
        
        # 采样
        if sample_size and sample_size < len(csv_files):
            import random
            csv_files = random.sample(csv_files, sample_size)
            self.log_info(f"随机采样 {sample_size} 个文件进行验证")
        
        # 验证每个文件
        results = []
        self.stats["total_files"] = len(csv_files)
        
        print(f"\n开始验证 {len(csv_files)} 个文件...\n")
        
        for i, csv_path in enumerate(csv_files, 1):
            # 进度显示
            if i % 100 == 0 or i == 1:
                elapsed = (datetime.now() - start_time).total_seconds()
                speed = i / elapsed if elapsed > 0 else 0
                eta = (len(csv_files) - i) / speed if speed > 0 else 0
                print(f"\n进度: {i}/{len(csv_files)} ({i/len(csv_files)*100:.1f}%) "
                      f"| 速度: {speed:.1f} 文件/秒 | 预计剩余: {eta:.0f}秒\n")
            
            print(f"[{i}/{len(csv_files)}] {csv_path.name}...", end=" ")
            
            result = self.verify_single_stock(csv_path, parquet_df)
            
            if result is None:
                self.stats["skipped_files"] += 1
                print("⏭️  跳过")
                continue
            
            results.append(result)
            
            # 判断是否匹配
            if result["row_count_match"] and (fast_mode or result["data_match"]):
                self.stats["matched_files"] += 1
                print("✅")
            else:
                self.stats["mismatched_files"] += 1
                print("❌")
                if len(result["mismatches"]) <= 3:
                    for mismatch in result["mismatches"]:
                        print(f"    {mismatch}")
        
        # 计算耗时
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        # 汇总结果
        print("\n" + "="*80)
        print("验证结果汇总")
        print("="*80)
        print(f"总文件数: {self.stats['total_files']}")
        print(f"✅ 匹配文件: {self.stats['matched_files']} "
              f"({self.stats['matched_files']/self.stats['total_files']*100:.1f}%)")
        print(f"❌ 不匹配文件: {self.stats['mismatched_files']} "
              f"({self.stats['mismatched_files']/self.stats['total_files']*100:.1f}%)")
        print(f"⏭️  跳过文件: {self.stats['skipped_files']}")
        print(f"\n总行数 (CSV): {self.stats['total_rows_csv']:,}")
        print(f"总行数 (Parquet): {self.stats['total_rows_parquet']:,}")
        print(f"\n耗时: {elapsed_time:.1f} 秒")
        print(f"平均速度: {self.stats['total_files']/elapsed_time:.1f} 文件/秒")
        
        if self.errors:
            print(f"\n❌ 错误数: {len(self.errors)}")
        if self.warnings:
            print(f"⚠️  警告数: {len(self.warnings)}")
        
        # 最终判断
        success = self.stats["mismatched_files"] == 0 and len(self.errors) == 0
        
        print("\n" + "="*80)
        if success:
            print("🎉 验证通过！CSV 和 Parquet 数据完全一致！")
            print("✅ 可以安全删除 CSV 文件！")
        else:
            print("⚠️  验证失败！发现数据不一致！")
            print("❌ 请勿删除 CSV 文件！")
        print("="*80 + "\n")
        
        return {
            "success": success,
            "stats": self.stats,
            "results": results,
            "errors": self.errors,
            "warnings": self.warnings,
            "elapsed_time": elapsed_time
        }


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="验证 CSV 和 Parquet 数据一致性")
    parser.add_argument("--sample", type=int, default=None, 
                       help="采样数量（默认验证所有文件）")
    parser.add_argument("--fast", action="store_true",
                       help="快速模式（只验证行数）")
    parser.add_argument("--csv-dir", type=str, 
                       default=r"d:\aquatrade\data\date",
                       help="CSV 文件目录")
    parser.add_argument("--parquet-file", type=str,
                       default=r"d:\aquatrade\data\parquet_data\stock_daily.parquet",
                       help="Parquet 文件路径")
    
    args = parser.parse_args()
    
    # 创建验证器
    verifier = CSVParquetVerifier(args.csv_dir, args.parquet_file)
    
    # 执行验证
    result = verifier.verify_all(sample_size=args.sample, fast_mode=args.fast)
    
    # 返回退出码
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
