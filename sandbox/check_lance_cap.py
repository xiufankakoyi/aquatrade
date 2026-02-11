
import lancedb
print(f"LanceDB Version: {lancedb.__version__}")
try:
    print(f"Has create_scalar_index: {hasattr(lancedb.table.Table, 'create_scalar_index')}")
except:
    print("Could not check Table class directly")
