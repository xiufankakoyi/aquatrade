
import requests
import urllib.parse

def query(sql):
    url = f"http://localhost:9000/exec?query={urllib.parse.quote(sql)}"
    try:
        resp = requests.get(url)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

print("--- Checking Top Data Holders ---")
res = query("SELECT stock_code, count() as cnt FROM base_daily ORDER BY cnt DESC LIMIT 5")
print(res)

print("\n--- Checking 000001 counts ---")
res = query("SELECT count() FROM base_daily WHERE stock_code = '000001'")
print(res)
