"""
LRU Cache 實作
使用 OrderedDict 實現 LRU (Least Recently Used) 快取機制
時間複雜度：get 和 put 操作均為 O(1)
"""

from collections import OrderedDict
from typing import Any, Hashable, Optional, Iterator, Iterable


class LRUCache:
    """
    LRU 快取類別
    
    使用 OrderedDict 維護元素的插入順序，並透過移動元素到末尾來標記為最近使用。
    當快取容量超過限制時，移除最久未使用的元素（第一個元素）。
    
    Attributes:
        capacity: 快取的最大容量
        cache: OrderedDict 用於儲存鍵值對，並維護使用順序
    """
    
    def __init__(self, capacity: int) -> None:
        """
        初始化 LRU Cache
        
        Args:
            capacity: 快取的最大容量，必須為正整數
        """
        if not isinstance(capacity, int) or capacity <= 0:
            raise TypeError("容量必須為正整數")
        
        self.capacity: int = capacity
        self.cache: OrderedDict[Hashable, Any] = OrderedDict()
    
    def __len__(self) -> int:
        """
        取得當前快取中的項目數
        
        Returns:
            快取中的項目數
        """
        return len(self.cache)
    
    def __contains__(self, key: Hashable) -> bool:
        """
        檢查鍵是否存在於快取中
        
        Args:
            key: 要檢查的鍵
            
        Returns:
            如果鍵存在則為 True，否則為 False
        """
        return key in self.cache
    
    def __repr__(self) -> str:
        """
        返回快取的字串表示式
        
        Returns:
            快取內容的字串表示
        """
        return f"LRUCache(capacity={self.capacity}, size={len(self.cache)}, data={dict(self.cache)})"
    
    def clear(self) -> None:
        """
        清空快取
        """
        self.cache.clear()
    
    def get(self, key: Hashable, default: Any = None) -> Optional[Any]:
        """
        取得指定鍵的值
        
        如果鍵存在，將該鍵值對移動到末尾（標記為最近使用），並返回值。
        如果鍵不存在，返回預設值（None 或指定的 default）。
        
        Args:
            key: 要查詢的鍵
            default: 當鍵不存在時返回的預設值，預設為 None
            
        Returns:
            對應的值，如果鍵不存在則返回預設值
        """
        if key not in self.cache:
            return default
        
        # 將訪問的鍵移動到末尾（最近使用）
        self.cache.move_to_end(key)
        return self.cache[key]
    
    def put(self, key: Hashable, value: Any) -> None:
        """
        插入或更新鍵值對
        
        如果鍵已存在，更新值並移動到末尾。
        如果鍵不存在，插入新鍵值對到末尾。
        如果超過容量，移除最久未使用的元素（第一個元素）。
        
        Args:
            key: 要插入的鍵
            value: 要插入的值
        """
        # 如果鍵已存在，先刪除再插入以確保順序正確
        if key in self.cache:
            # 移動到末尾（最近使用）
            self.cache.move_to_end(key)
            self.cache[key] = value
        else:
            # 插入新鍵值對
            self.cache[key] = value
            # 如果超過容量，移除最久未使用的元素
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)
    
    # 字典式 API 方法
    
    def __getitem__(self, key: Hashable) -> Any:
        """
        支援 cache[key] 語法
        
        Args:
            key: 要查詢的鍵
            
        Returns:
            對應的值
            
        Raises:
            KeyError: 如果鍵不存在
        """
        if key not in self.cache:
            raise KeyError(key)
        self.cache.move_to_end(key)
        return self.cache[key]
    
    def __setitem__(self, key: Hashable, value: Any) -> None:
        """
        支援 cache[key] = value 語法
        
        Args:
            key: 要插入的鍵
            value: 要插入的值
        """
        self.put(key, value)
    
    def __delitem__(self, key: Hashable) -> None:
        """
        支援 del cache[key] 語法
        
        Args:
            key: 要刪除的鍵
            
        Raises:
            KeyError: 如果鍵不存在
        """
        if key not in self.cache:
            raise KeyError(key)
        del self.cache[key]
    
    def pop(self, key: Hashable, default: Any = None) -> Any:
        """
        移除並返回指定鍵的值
        
        Args:
            key: 要移除的鍵
            default: 如果鍵不存在時返回的預設值
            
        Returns:
            對應的值，如果鍵不存在則返回 default
        """
        if key in self.cache:
            value = self.cache.pop(key)
            return value
        return default
    
    def keys(self) -> Iterable[Hashable]:
        """
        返回所有鍵的迭代器
        
        Returns:
            鍵的迭代器
        """
        return self.cache.keys()
    
    def values(self) -> Iterable[Any]:
        """
        返回所有值的迭代器
        
        Returns:
            值的迭代器
        """
        return self.cache.values()
    
    def items(self) -> Iterable[tuple[Hashable, Any]]:
        """
        返回所有鍵值對的迭代器
        
        Returns:
            鍵值對的迭代器
        """
        return self.cache.items()
    
    def __eq__(self, other: object) -> bool:
        """
        檢查兩個 LRU Cache 是否相等
        
        Args:
            other: 要比較的物件
            
        Returns:
            如果兩個快取內容相同則為 True
        """
        if not isinstance(other, LRUCache):
            return False
        return self.cache == other.cache
    
    def __bool__(self) -> bool:
        """
        支援 bool 檢查
        
        Returns:
            如果快取非空則為 True
        """
        return bool(self.cache)
    
    def setdefault(self, key: Hashable, default: Any = None) -> Any:
        """
        如果鍵不存在，設置預設值並返回預設值
        如果鍵已存在，返回現有值
        
        Args:
            key: 要查詢的鍵
            default: 如果鍵不存在時設置的值，預設為 None
            
        Returns:
            現有的值或預設值
        """
        if key not in self.cache:
            self.cache[key] = default
            return default
        # 如果存在，移動到末尾（最近使用）
        self.cache.move_to_end(key)
        return self.cache[key]
    
    def update(self, other: Optional[Iterable[tuple[Hashable, Any]]] = None, **kwargs: Any) -> None:
        """
        批量更新/插入鍵值對
        
        Args:
            other: 可迭代的鍵值對序列，或字典
            **kwargs: 額外的鍵值對
        """
        if other is not None:
            if hasattr(other, 'keys') and hasattr(other, 'items'):
                # 字典類物件
                for key, value in other.items():
                    self.put(key, value)
            else:
                # 可迭代的鍵值對
                for key, value in other:
                    self.put(key, value)
        
        # 處理 kwargs
        for key, value in kwargs.items():
            self.put(key, value)


def main() -> None:
    """
    測試 LRU Cache 功能
    """
    print("=== LRU Cache 測試 ===")
    
    # 建立容量為 2 的 LRU Cache
    cache = LRUCache(2)
    
    # 測試 put 操作
    print("\n1. 插入鍵值對:")
    cache.put(1, 100)
    print(f"put(1, 100)")
    cache.put(2, 200)
    print(f"put(2, 200)")
    print(f"當前快取內容: {dict(cache.cache)}")
    
    # 測試 get 操作
    print("\n2. 取得值:")
    result = cache.get(1)
    print(f"get(1) = {result}")
    print(f"當前快取內容: {dict(cache.cache)}")
    
    # 測試更新現有鍵
    print("\n3. 更新現有鍵:")
    cache.put(1, 150)
    print(f"put(1, 150)")
    print(f"當前快取內容: {dict(cache.cache)}")
    
    # 測試超過容量時的 LRU 行為
    print("\n4. 超過容量時移除最久未使用的元素:")
    cache.put(3, 300)
    print(f"put(3, 300)")
    print(f"當前快取內容: {dict(cache.cache)}")
    print("鍵 2 已被移除，因為它是最久未使用的")
    
    # 測試不存在的鍵
    print("\n5. 取得不存在的鍵:")
    result = cache.get(2)
    print(f"get(2) = {result}")
    
    # 測試更多操作
    print("\n6. 更多操作測試:")
    cache.put(4, 400)
    print(f"put(4, 400)")
    print(f"當前快取內容: {dict(cache.cache)}")
    print(f"get(1) = {cache.get(1)}")
    print(f"get(3) = {cache.get(3)}")
    print(f"get(4) = {cache.get(4)}")
    
    # 測試新增方法
    print("\n7. 測試新增方法:")
    print(f"len(cache) = {len(cache)}")
    print(f"1 in cache = {1 in cache}")
    print(f"999 in cache = {999 in cache}")
    print(f"repr(cache) = {repr(cache)}")
    
    # 測試 clear 方法
    print("\n8. 測試 clear 方法:")
    cache.clear()
    print(f"clear() 後: {repr(cache)}")
    
    # 測試容量為 1 的邊界情況
    print("\n9. 測試容量為 1 的邊界情況:")
    small_cache = LRUCache(1)
    small_cache.put(1, 100)
    print(f"put(1, 100) 後: {repr(small_cache)}")
    small_cache.put(2, 200)
    print(f"put(2, 200) 後: {repr(small_cache)}")
    print(f"get(1) = {small_cache.get(1)}")
    print(f"get(2) = {small_cache.get(2)}")
    
    # 測試迭代
    print("\n10. 測試迭代:")
    cache.put(10, 100)
    cache.put(20, 200)
    cache.put(30, 300)
    print("迭代鍵:")
    for key in list(cache.keys()):
        print(f"  key={key}, value={cache.get(key)}")
    
    # 測試字典式 API
    print("\n11. 測試字典式 API:")
    cache2 = LRUCache(3)
    cache2[1] = 100
    cache2[2] = 200
    print(f"cache2[1] = {cache2[1]}")
    print(f"keys: {list(cache2.keys())}")
    print(f"values: {list(cache2.values())}")
    print(f"items: {list(cache2.items())}")
    
    # 測試 pop 方法
    print("\n12. 測試 pop 方法:")
    print(f"cache2.pop(1) = {cache2.pop(1)}")
    print(f"cache2.pop(999, 'default') = {cache2.pop(999, 'default')}")
    print(f"cache2 內容: {dict(cache2.cache)}")
    
    # 測試 __delitem__
    print("\n13. 測試 del 語法:")
    del cache2[2]
    print(f"del cache2[2] 後: {dict(cache2.cache)}")
    
    # 測試 __eq__
    print("\n14. 測試相等比較:")
    cache3 = LRUCache(3)
    cache3[1] = 100
    cache3[2] = 200
    print(f"cache2 == cache3: {cache2 == cache3}")
    
    # 測試 KeyError
    print("\n15. 測試 KeyError:")
    try:
        _ = cache2[999]
    except KeyError as e:
        print(f"KeyError: {e}")
    
    # 測試 setdefault
    print("\n16. 測試 setdefault:")
    cache4 = LRUCache(3)
    result = cache4.setdefault(1, 100)
    print(f"setdefault(1, 100) = {result}")
    result = cache4.setdefault(1, 200)
    print(f"setdefault(1, 200) = {result} (應為 100，因為鍵已存在)")
    print(f"cache4 內容: {dict(cache4.cache)}")
    
    # 測試 update
    print("\n17. 測試 update:")
    cache5 = LRUCache(5)
    cache5.update({1: 100, 2: 200})
    cache5.update([(3, 300), (4, 400)])
    cache5.update(a=10, b=20)
    print(f"cache5 內容: {dict(cache5.cache)}")
    
    # 測試 bool 檢查
    print("\n18. 測試 bool 檢查:")
    empty_cache = LRUCache(5)
    print(f"bool(empty_cache) = {bool(empty_cache)}")
    print(f"bool(cache5) = {bool(cache5)}")
    
    print("\n=== 測試完成 ===")


if __name__ == "__main__":
    main()
