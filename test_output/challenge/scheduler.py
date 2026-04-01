"""
PriorityTaskScheduler 實作：
一個基於優先級的執行緒安全任務排程器。
使用 heapq 實現優先級佇列，配合 threading.Lock 確保執行緒安全。
"""

import heapq
import threading
from typing import Callable, Any, Optional, Tuple
import time


class PriorityTaskScheduler:
    """
    優先級任務排程器
    
    此排程器允許添加具有不同優先級的任務，並按照優先級順序執行。
    較小的 priority 值表示較高的優先級。
    
    Attributes:
        max_workers: 最大工作執行緒數量（目前實作為單執行緒執行）
        _heap: 用於儲存任務的堆積結構
        _lock: 用於保護共享狀態的鎖
        _shutdown: 用於停止排程器的標誌
    """
    
    def __init__(self, max_workers: int = 1):
        """
        初始化排程器
        
        Args:
            max_workers: 最大工作執行緒數量（目前實作為單執行緒執行）
        """
        self.max_workers = max_workers
        self._heap: list[Tuple[int, int, Callable, Tuple, dict]] = []
        self._counter = 0  # 用於穩定排序的計數器
        self._lock = threading.Lock()
        self._shutdown = False
        self._task_added = threading.Condition(self._lock)
    
    def add_task(self, priority: int, task_func: Callable, *args: Any, **kwargs: Any) -> None:
        """
        添加一個任務到排程器
        
        priority 越小越優先。任務會在 run_next() 被調用時執行。
        
        Args:
            priority: 任務的優先級（越小越優先）
            task_func: 要執行的函數
            *args: 位置參數傳遞給 task_func
            **kwargs: 關鍵字參數傳遞給 task_func
            
        Raises:
            RuntimeError: 當排程器已停止時無法添加任務
        """
        with self._lock:
            if self._shutdown:
                raise RuntimeError("排程器已停止，無法添加新任務")
            
            # 使用計數器確保相同優先級的任務按照添加順序執行（穩定排序）
            heapq.heappush(self._heap, (priority, self._counter, task_func, args, kwargs))
            self._counter += 1
            self._task_added.notify()
    
    def run_next(self) -> bool:
        """
        執行下一個最高優先級的任務
        
        如果沒有可執行的任務，返回 False。
        任務崩潰不會影響排程器的正常運作。
        
        Returns:
            bool: 如果成功執行了一個任務，返回 True；如果沒有任務可執行，返回 False
        """
        task_func = None
        args = ()
        kwargs = {}
        
        with self._lock:
            if self._shutdown:
                return False
            
            if not self._heap:
                return False
            
            # 取出最高優先級的任務
            _, _, task_func, args, kwargs = heapq.heappop(self._heap)
        
        if task_func is None:
            return False
        
        try:
            # 執行任務，捕獲任何異常
            task_func(*args, **kwargs)
            return True
        except Exception as e:
            # 任務崩潰不影響排程器
            print(f"任務執行時發生錯誤: {e}")
            return True  # 仍然返回 True，因為我們成功「執行」了這個任務（即使它崩潰了）
    
    def cancel_pending(self) -> int:
        """
        取消所有待處理的任務
        
        Returns:
            int: 被取消的任務數量
        """
        with self._lock:
            count = len(self._heap)
            self._heap.clear()
            return count
    
    def shutdown(self) -> None:
        """
        停止排程器並清除所有待處理的任務
        """
        with self._lock:
            self._shutdown = True
            self._heap.clear()
            self._task_added.notify_all()
    
    def pending_count(self) -> int:
        """
        獲取待處理的任務數量
        
        Returns:
            int: 待處理的任務數量
        """
        with self._lock:
            return len(self._heap)


def test_priority_scheduler():
    """
    測試 PriorityTaskScheduler 的多執行緒功能
    
    此測試會啟動多個執行緒來同時添加和執行任務，驗證排程器的執行緒安全性。
    """
    print("=== PriorityTaskScheduler 多執行緒測試 ===")
    
    scheduler = PriorityTaskScheduler(max_workers=1)
    results = []
    results_lock = threading.Lock()
    
    # 定義一個測試任務函數
    def task_func(task_id: int, delay: float = 0.01):
        """模擬一個需要執行的任務"""
        time.sleep(delay)
        with results_lock:
            results.append(task_id)
        print(f"任務 {task_id} 完成")
    
    # 創建多個執行緒來添加任務
    def add_tasks(thread_id: int, start_priority: int):
        """從多個執行緒添加任務"""
        for i in range(5):
            priority = start_priority + i
            task_id = thread_id * 100 + i
            scheduler.add_task(priority, task_func, task_id, delay=0.01)
            print(f"執行緒 {thread_id} 添加任務 {task_id}，優先級 {priority}")
    
    # 創建多個執行緒來執行任務
    def execute_tasks(thread_id: int):
        """從多個執行緒執行任務"""
        for _ in range(10):
            if scheduler.run_next():
                print(f"執行緒 {thread_id} 執行了一個任務")
            else:
                print(f"執行緒 {thread_id} 沒有任務可執行")
            time.sleep(0.01)
    
    # 啟動添加任務的執行緒
    threads = []
    for i in range(3):
        t = threading.Thread(target=add_tasks, args=(i, i * 10))
        threads.append(t)
        t.start()
    
    # 啟動執行任務的執行緒
    exec_threads = []
    for i in range(2):
        t = threading.Thread(target=execute_tasks, args=(i,))
        exec_threads.append(t)
        t.start()
    
    # 等待所有添加任務的執行緒完成
    for t in threads:
        t.join()
    
    # 等待所有執行任務的執行緒完成
    for t in exec_threads:
        t.join()
    
    # 執行剩餘的任務
    print("\n執行剩餘的任務...")
    while scheduler.run_next():
        pass
    
    print(f"\n所有任務完成順序: {results}")
    print(f"總共執行了 {len(results)} 個任務")
    
    # 測試取消功能
    print("\n測試取消功能...")
    for i in range(5):
        scheduler.add_task(i, task_func, f"cancel_test_{i}")
    print(f"添加 5 個任務，待處理數量: {scheduler.pending_count()}")
    cancelled = scheduler.cancel_pending()
    print(f"取消了 {cancelled} 個任務，待處理數量: {scheduler.pending_count()}")
    
    # 測試任務崩潰不影響排程器
    print("\n測試任務崩潰不影響排程器...")
    
    def crashing_task():
        """會崩潰的任務"""
        raise ValueError("任務故意崩潰")
    
    def normal_task(task_id: int):
        """正常任務"""
        print(f"正常任務 {task_id} 執行成功")
    
    scheduler.add_task(1, crashing_task)
    scheduler.add_task(2, normal_task, "after_crash")
    scheduler.add_task(3, normal_task, "after_crash_2")
    
    print("執行任務（包含崩潰任務）...")
    scheduler.run_next()  # 應該會崩潰但排程器不崩潰
    scheduler.run_next()  # 應該能繼續執行
    scheduler.run_next()  # 應該能繼續執行
    
    print("\n測試完成！")


if __name__ == "__main__":
    test_priority_scheduler()
