from questdb.ingress import Sender
import sys

print("Probing Sender signature...")

tests = [
    # 1. Protocol, Host, Port
    (('tcp', 'localhost', 9009), "('tcp', 'localhost', 9009)"),
    # 2. Host, Port
    (('localhost', 9009), "('localhost', 9009)"),
    # 3. Host, Port, Auth
    (('localhost', 9009, None), "('localhost', 9009, None)"),
     # 4. Host, Port, Auth, Others
    (('localhost', 9009, None, None), "('localhost', 9009, None, None)"),
]

for args, label in tests:
    try:
        print(f"Trying {label}...")
        with Sender(*args) as s:
            print(f"  ✅ SUCCESS: {label}")
            break
    except Exception as e:
        print(f"  ❌ FAILED {label}: {e}")
