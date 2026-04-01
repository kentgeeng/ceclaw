"""
Task Manager 模組 - 提供 TaskManager 類別
"""
from datetime import datetime
from typing import List, Optional

# 支援直接執行時的 import
try:
    from .task import Task, Priority, TaskStatus
    from .storage import Storage
except ImportError:
    from task import Task, Priority, TaskStatus
    from storage import Storage


class TaskManager:
    """
    TaskManager 類別 - 管理任務的增刪改查
    
    提供任務管理的主要介面，包含新增、列出、完成、刪除任務等功能
    """
    
    def __init__(self, storage_file: str = "tasks.json"):
        """
        初始化 TaskManager
        
        Args:
            storage_file: 儲存檔案路徑
        """
        self.storage = Storage(storage_file)
        self._next_id = self._get_next_id()
    
    def _get_next_id(self) -> int:
        """
        取得下一個可用的任務 ID
        
        Returns:
            下一個 ID
        """
        tasks = self.storage.load_tasks()
        if not tasks:
            return 1
        return max(t.id for t in tasks) + 1
    
    def add_task(self, title: str, priority: Priority = Priority.MEDIUM) -> Task:
        """
        新增新任務
        
        Args:
            title: 任務標題
            priority: 優先級，預設為中等
            
        Returns:
            建立的新 Task 物件
        """
        task = Task(
            id=self._next_id,
            title=title,
            priority=priority,
            status=TaskStatus.PENDING,
            created_at=datetime.now()
        )
        self.storage.append_task(task)
        self._next_id += 1
        return task
    
    def list_tasks(self, sort_by_priority: bool = True) -> List[Task]:
        """
        列出所有任務
        
        Args:
            sort_by_priority: 是否依優先級排序（由高到低）
            
        Returns:
            Task 物件列表
        """
        tasks = self.storage.load_tasks()
        
        if sort_by_priority:
            # 依優先級排序（high=3 > medium=2 > low=1）
            tasks = sorted(tasks, key=lambda t: t.priority.value, reverse=True)
        
        return tasks
    
    def complete_task(self, task_id: int) -> bool:
        """
        將任務標記為完成
        
        Args:
            task_id: 要完成的任務 ID
            
        Returns:
            若成功更新則返回 True，若找不到則返回 False
        """
        tasks = self.storage.load_tasks()
        for task in tasks:
            if task.id == task_id:
                task.status = TaskStatus.COMPLETED
                self.storage.update_task(task)
                return True
        return False
    
    def delete_task(self, task_id: int) -> bool:
        """
        刪除任務
        
        Args:
            task_id: 要刪除的任務 ID
            
        Returns:
            若成功刪除則返回 True，若找不到則返回 False
        """
        return self.storage.delete_task_by_id(task_id)
    
    def get_task(self, task_id: int) -> Optional[Task]:
        """
        根據 ID 取得任務
        
        Args:
            task_id: 任務 ID
            
        Returns:
            若找到則返回 Task 物件，否則返回 None
        """
        tasks = self.storage.load_tasks()
        for task in tasks:
            if task.id == task_id:
                return task
        return None


def main():
    """
    測試 TaskManager 功能
    """
    # 建立 TaskManager 實例（使用測試檔案）
    manager = TaskManager("test_tasks.json")
    
    print("=== 新增任務 ===")
    task1 = manager.add_task("學習 Python", Priority.HIGH)
    print(f"新增任務: {task1}")
    
    task2 = manager.add_task("閱讀文件", Priority.LOW)
    print(f"新增任務: {task2}")
    
    task3 = manager.add_task("撰寫程式碼", Priority.MEDIUM)
    print(f"新增任務: {task3}")
    
    print("\n=== 列出所有任務（依優先級排序） ===")
    tasks = manager.list_tasks()
    for task in tasks:
        print(task)
    
    print("\n=== 完成任務 ===")
    result = manager.complete_task(1)
    print(f"完成任務 ID 1: {'成功' if result else '失敗'}")
    
    print("\n=== 列出所有任務（完成後） ===")
    tasks = manager.list_tasks()
    for task in tasks:
        print(task)
    
    print("\n=== 刪除任務 ===")
    result = manager.delete_task(2)
    print(f"刪除任務 ID 2: {'成功' if result else '失敗'}")
    
    print("\n=== 最終任務列表 ===")
    tasks = manager.list_tasks()
    for task in tasks:
        print(task)


if __name__ == "__main__":
    main()
