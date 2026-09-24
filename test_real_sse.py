# test_real_sse.py
import requests
import json

BASE_URL = "http://localhost:8000"

print("=" * 50)
print("TEST 1: Small valid JSON (normal case)")
print("=" * 50)
r = requests.post(
    f"{BASE_URL}/api/v1/mcp/messages",
    json={"jsonrpc": "2.0", "method": "tools/list", "id": 1}
)
print(f"Status: {r.status_code}")
print(f"Response: {r.text}")

print()
print("=" * 50)
print("TEST 2: Incomplete JSON (split SSE boundary)")
print("=" * 50)
r = requests.post(
    f"{BASE_URL}/api/v1/mcp/messages",
    data='{"jsonrpc":"2.0","result":{"very_large_field":"' + "x" * 10000,
    headers={"Content-Type": "application/json"}
)
print(f"Status: {r.status_code}")
print(f"Response: {r.text}")

print()
print("=" * 50)
print("TEST 3: Large but complete JSON (real world case)")
print("=" * 50)
large_payload = {
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 3,
    "params": {"data": "x" * 100000}  # 100KB payload
}
r = requests.post(
    f"{BASE_URL}/api/v1/mcp/messages",
    json=large_payload
)
print(f"Status: {r.status_code}")
print(f"Response: {r.text}")
