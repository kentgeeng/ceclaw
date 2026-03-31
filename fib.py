#!/usr/bin/env python3
"""
Fibonacci 數列計算程式
"""

def fibonacci(n):
    """
    計算第 n 個 Fibonacci 數列的值
    
    參數:
        n (int): 要計算的位置（從 0 開始）
    
    回傳:
        int: 第 n 個 Fibonacci 數列的值
    """
    if n < 0:
        raise ValueError("n 必須是非負整數")
    
    if n == 0:
        return 0
    
    if n == 1:
        return 1
    
    # 使用迭代方式計算 Fibonacci 數列
    prev = 0  # F(n-2)
    curr = 1  # F(n-1)
    
    for _ in range(2, n + 1):
        # 計算下一個 Fibonacci 數列值
        prev, curr = curr, prev + curr
    
    return curr


if __name__ == "__main__":
    # 測試範例：顯示前 10 個 Fibonacci 數列
    print("Fibonacci 數列的前 10 個值：")
    for i in range(10):
        print(f"F({i}) = {fibonacci(i)}")
    
    # 測試特定值
    n = 10
    print(f"\n第 {n} 個 Fibonacci 數列的值是：{fibonacci(n)}")
