
import requests
import json
import urllib.parse

def query(sql):
    url = f"http://localhost:9000/exec?query={urllib.parse.quote(sql)}"
    try:
        resp = requests.get(url)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

print("--- Probing for '000001' variants ---")

# 1. Broad search
print("\n1. Searching for any code starting with '000001':")
res = query("SELECT distinct stock_code FROM base_daily WHERE stock_code ~ '000001'")
print(res)

# 2. Check specific formats
print("\n2. Checking '000001':")
res = query("SELECT count() FROM base_daily WHERE stock_code = '000001'")
print(res)

print("\n3. Checking '1':")
res = query("SELECT count() FROM base_daily WHERE stock_code = '1'")
print(res)

print("\n4. Checking '000001.SZ':")
res = query("SELECT count() FROM base_daily WHERE stock_code = '000001.SZ'")
print(res)

# 5. Check data range for '000001'
print("\n5. Checking Min/Max timestamp for '000001':")
res = query("SELECT min(timestamp), max(timestamp), count() FROM base_daily WHERE stock_code = '000001'")
print(res)

# 6. Test Date Filter Syntax
print("\n6. Checking 2021 count for '000001':")
res = query("SELECT count() FROM base_daily WHERE stock_code = '000001' AND timestamp BETWEEN '2021-01-01' AND '2021-12-31'")
print(res)

# 7. Check if ISO format matters
print("\n7. Checking ISO date format:")
res = query("SELECT count() FROM base_daily WHERE stock_code = '000001' AND timestamp BETWEEN '2021-01-01T00:00:00.000000Z' AND '2021-12-31T23:59:59.999999Z'")
print(res)
