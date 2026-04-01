"""排序演算法 - 有 bug 版本"""
from typing import List

def quicksort(arr: List[int]) -> List[int]:
    """快速排序實作"""
    if len(arr) <= 1:
        return arr
    
    pivot = arr[0]
    left = [x for x in arr[1:] if x < pivot]
    right = [x for x in arr[1:] if x >= pivot]
    
    return quicksort(left) + [pivot] + quicksort(right)

def binary_search(arr: List[int], target: int) -> int:
    """二分搜尋 - 返回索引或 -1"""
    low, high = 0, len(arr)
    
    while low < high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid
    
    return -1

def find_duplicates(arr: List[int]) -> List[int]:
    """找出重複元素"""
    seen = set()
    duplicates = set()
    
    for x in arr:
        # 檢查元素是否已見過
        if x in seen:
            duplicates.add(x)
        seen.add(x)
    
    return list(duplicates)

if __name__ == "__main__":
    # 測試
    print("quicksort([3, 1, 4, 1, 5, 9, 2, 6]) =", quicksort([3, 1, 4, 1, 5, 9, 2, 6]))
    print("binary_search([1, 2, 3, 4, 5], 3) =", binary_search([1, 2, 3, 4, 5], 3))
    print("find_duplicates([1, 2, 2, 3, 3, 3, 4]) =", find_duplicates([1, 2, 2, 3, 3, 3, 4]))
