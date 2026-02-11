import requests

QUESTDB_HOST = "localhost"
QUESTDB_HTTP_PORT = 9000

tables = ["base_daily", "factors_momentum", "factors_valuation"]

print("Cleaning up QuestDB tables...")
for table in tables:
    try:
        r = requests.get(f"http://{QUESTDB_HOST}:{QUESTDB_HTTP_PORT}/exec", params={"query": f"DROP TABLE {table}"})
        if r.status_code == 200:
            print(f"✅ Dropped {table}: {r.json().get('ddl')}")
        else:
            print(f"⚠️ Failed to drop {table}: {r.text}")
    except Exception as e:
        print(f"❌ Error dropping {table}: {e}")
