#!/usr/bin/env python3
"""在記憶體中建立包含 10 萬筆紀錄的 Dict，隨機抽樣 3 筆輸出"""

import random
import string

def generate_random_string(length=10):
    """生成隨機字串"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def main():
    # 建立包含 10 萬筆紀錄的 Dict
    print("建立 10 萬筆紀錄的 Dict...")
    data = {}
    for i in range(100000):
        key = f"record_{i:06d}"
        data[key] = {
            "id": i,
            "name": generate_random_string(8),
            "email": f"user{i}@example.com",
            "score": random.randint(1, 100),
            "created_at": f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        }
    
    print(f"已建立 {len(data)} 筆紀錄")
    
    # 隨機抽樣 3 筆
    print("\n隨機抽樣 3 筆紀錄:")
    sampled_keys = random.sample(list(data.keys()), 3)
    
    for i, key in enumerate(sampled_keys, 1):
        print(f"\n--- 抽樣 {i} ---")
        print(f"Key: {key}")
        print(f"內容: {data[key]}")

if __name__ == "__main__":
    main()
