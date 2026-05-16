from arcticdb import Arctic

arctic = Arctic("lmdb://C:/Users/Liu/Desktop/projects/aquatrade/data/arctic_db")

# 检查 000001.SZ 数据
lib = arctic["daily"]
if "000001.SZ" in lib.list_symbols():
    data = lib.read("000001.SZ")
    df = data.data
    print(f"000001.SZ 数据量: {len(df)}")
    print(f"日期范围: {df.index.min()} ~ {df.index.max()}")
    print(df)
else:
    print("000001.SZ 不在 daily 库中")
