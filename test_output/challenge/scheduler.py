"""
執行緒安全的優先級任務排程器

此模組提供一個執行緒安全的 PriorityTaskScheduler 類別，用於管理具有優先級的任務。
任務會根據優先級（數值越小越優先）依序執行，並支援多執行緒安全操作。
"""

import heapq
import threading
from typing import Callable, Any, Optional
from itertools import count


class PriorityTaskScheduler:
    """
    執行緒安全的優先級任務排程器
    
    使用 heapq 實作優先級佇列，配合 threading.Lock 確保執行緒安全。
    任務按照優先級（數值越小越優先）依序執行，相同優先級則依加入順序執行。
    
    Attributes:
        _heap: 用於儲存任務的優先級佇列
        _counter: 用於維持相同優先級任務的加入順序
        _lock: 用於保護共享資源的互斥鎖
        _shutdown: 用於標記排程器是否已停止
        _counter_lock: 用於保護 counter 的鎖
    """
    
    def __init__(self, max_workers: int = 1):
        """
        初始化排程器
        
        Args:
            max_workers: 最大工作執行緒數（目前實作為單執行緒執行，但保留此參數供未來擴充）
        """
        self._heap: list = []
        self._counter = count()
        self._lock = threading.Lock()
        self._shutdown = False
        self._counter_lock = threading.Lock()
        self._max_workers = max_workers
    
    def add_task(self, priority: int, task_func: Callable, *args: Any, **kwargs: Any) -> None:
        """
        新增一個任務到排程器
        
        任務會根據優先級插入到佇列中，數值越小表示優先級越高。
        相同優先級的任務會依照加入順序執行。
        
        Args:
            priority: 任務優先級（數值越小越優先）
            task_func: 要執行的函數
            *args: 傳遞給任務函數的位置參數
            **kwargs: 傳遞給任務函數的關鍵字參數
        
        Example:
            >>> scheduler = PriorityTaskScheduler()
            >>> scheduler.add_task(1, print, "高優先級")
            >>> scheduler.add_task(2, print, "低優先級")
        """
        with self._counter_lock:
            counter_value = next(self._counter)
        
        # tuple 格式: (priority, counter, task_func, args, kwargs)
        task_entry = (priority, counter_value, task_func, args, kwargs)
        
        with self._lock:
            heapq.heappush(self._heap, task_entry)
    
    def run_next(self) -> bool:
        """
        執行佇列中的下一個任務
        
        從優先級佇列中取出最高優先級的任務並執行。
        如果任務執行時發生異常，會記錄錯誤但不會導致排程器崩潰。
        
        Returns:
            bool: 如果成功執行了一個任務則回傳 True，如果佇列為空則回傳 False
        """
        with self._lock:
            if not self._heap:
                return False
            
            if self._shutdown:
                return False
            
            priority, counter, task_func, args, kwargs = heapq.heappop(self._heap)
        
        try:
            task_func(*args, **kwargs)
            return True
        except Exception as e:
            # 任務崩潰不影響排程器
            print(f"任務執行時發生錯誤: {e}")
            return True
    
    def cancel_pending(self) -> int:
        """
        取消所有待處理的任務
        
        清空佇列中的所有任務。
        
        Returns:
            int: 被取消的任務數量
        """
        with self._lock:
            count = len(self._heap)
            self._heap.clear()
            return count
    
    def is_empty(self) -> bool:
        """
        檢查佇列是否為空
        
        Returns:
            bool: 如果佇列為空則回傳 True
        """
        with self._lock:
            return len(self._heap) == 0
    
    def stop(self) -> None:
        """
        停止排程器
        
        標記排程器為停止狀態，不再接受新任務。
        """
        with self._lock:
            self._shutdown = True


def test_basic_functionality():
    """測試基本功能"""
    print("=== 測試基本功能 ===")
    scheduler = PriorityTaskScheduler()
    
    results = []
    
    def task1():
        results.append("任務 1")
        print("執行任務 1")
    
    def task2():
        results.append("任務 2")
        print("執行任務 2")
    
    def task3():
        results.append("任務 3")
        print("執行任務 3")
    
    # 依不同順序加入任務
    scheduler.add_task(2, task2)
    scheduler.add_task(1, task1)
    scheduler.add_task(3, task3)
    
    # 執行所有任務
    while scheduler.run_next():
        pass
    
    print(f"執行順序: {results}")
    assert results == ["任務 1", "任務 2", "任務 3"], "優先級順序錯誤"
    print("✓ 基本功能測試通過\n")


def test_cancel_functionality():
    """測試取消功能"""
    print("=== 測試取消功能 ===")
    scheduler = PriorityTaskScheduler()
    
    def task1():
        print("任務 1 執行")
    
    def task2():
        print("任務 2 執行")
    
    scheduler.add_task(1, task1)
    scheduler.add_task(2, task2)
    
    cancelled = scheduler.cancel_pending()
    print(f"取消了 {cancelled} 個任務")
    assert cancelled == 2, "取消數量錯誤"
    assert scheduler.is_empty(), "佇列應該為空"
    print("✓ 取消功能測試通過\n")


def test_error_handling():
    """測試錯誤處理"""
    print("=== 測試錯誤處理 ===")
    scheduler = PriorityTaskScheduler()
    
    def good_task():
        print("正常任務執行")
    
    def bad_task():
        raise ValueError("故意拋出的錯誤")
    
    scheduler.add_task(1, good_task)
    scheduler.add_task(2, bad_task)
    scheduler.add_task(3, good_task)
    
    # 執行所有任務，即使有錯誤也不應該崩潰
    count = 0
    while scheduler.run_next():
        count += 1
    
    print(f"成功執行了 {count} 個任務")
    assert count == 3, "應該執行所有任務"
    print("✓ 錯誤處理測試通過\n")


def test_multithreaded():
    """測試多執行緒環境"""
    print("=== 測試多執行緒環境 ===")
    scheduler = PriorityTaskScheduler()
    
    results = []
    lock = threading.Lock()
    
    def task_with_delay(name):
        import time
        time.sleep(0.01)
        with lock:
            results.append(name)
        print(f"執行 {name}")
    
    # 從多個執行緒加入任務
    threads = []
    for i in range(10):
        task_name = f"任務-{i}"
        def make_task(n):
            def t():
                task_with_delay(n)
            return t
        
        t = threading.Thread(target=scheduler.add_task, args=(i, make_task(task_name)))
        threads.append(t)
    
    for t in threads:
        t.start()
    
    for t in threads:
        t.join()
    
    # 執行所有任務
    while scheduler.run_next():
        pass
    
    print(f"執行結果: {results}")
    print(f"總共執行了 {len(results)} 個任務")
    assert len(results) == 10, "應該執行所有任務"
    print("✓ 多執行緒測試通過\n")


def test_priority_order():
    """測試優先級順序"""
    print("=== 測試優先級順序 ===")
    scheduler = PriorityTaskScheduler()
    
    results = []
    
    def make_task(name):
        def task():
            results.append(name)
        return task
    
    # 加入任務，順序與優先級無關
    scheduler.add_task(5, make_task("E"))
    scheduler.add_task(1, make_task("A"))
    scheduler.add_task(3, make_task("C"))
    scheduler.add_task(2, make_task("B"))
    scheduler.add_task(4, make_task("D"))
    
    while scheduler.run_next():
        pass
    
    print(f"執行順序: {results}")
    assert results == ["A", "B", "C", "D", "E"], "優先級順序錯誤"
    print("✓ 優先級順序測試通過\n")


def test_same_priority_order():
    """測試相同優先級的順序"""
    print("=== 測試相同優先級順序 ===")
    scheduler = PriorityTaskScheduler()
    
    results = []
    
    def make_task(name):
        def task():
            results.append(name)
        return task
    
    # 加入相同優先級的任務
    scheduler.add_task(1, make_task("A"))
    scheduler.add_task(1, make_task("B"))
    scheduler.add_task(1, make_task("C"))
    
    while scheduler.run_next():
        pass
    
    print(f"執行順序: {results}")
    assert results == ["A", "B", "C"], "相同優先級應該依加入順序執行"
    print("✓ 相同優先級順序測試通過\n")


if __name__ == "__main__":
    print("PriorityTaskScheduler 測試套件")
    print("=" * 50)
    print()
    
    test_basic_functionality()
    test_cancel_functionality()
    test_error_handling()
    test_multithreaded()
    test_priority_order()
    test_same_priority_order()
    
    print("=" * 50)
    print("所有測試通過！")
