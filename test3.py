import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Dữ liệu POST
data = {
    "url": "https://www.youtube.com/watch?v=I5LFTwnJeyM",
    "max_resolution": 720,
    "progressive_only": False,
    "edit_65s": False
}

def send_request(i):
    start = time.time()
    response = requests.post("http://localhost:8000/download", json=data)
    end = time.time()
    try:
        result = response.json()
    except Exception:
        result = response.text
    return i, result, end - start

# Chạy 3 request song song
with ThreadPoolExecutor(max_workers=3) as executor:
    futures = [executor.submit(send_request, i) for i in range(3)]
    for future in as_completed(futures):
        i, result, elapsed = future.result()
        print(f"Request {i}: {elapsed:.2f}s, Response: {result}")
