"""
Storage 模組 - 使用 JSON 檔案進行持久化儲存
"""
import json
import os
from pathlib import Path
import datetime
from typing import List, Optional

# 支援直接執行時的 import
try:
    from .task import Task, Priority, TaskStatus
except ImportError:
    from task import Task, Priority, TaskStatus


class Storage:
    """
    儲存類別 - 負責 Task 的讀取與寫入
    
    使用 JSON 檔案進行持久化儲存，支援自動建立目錄與檔案
    """
    
    def __init__(self, file_path: str = "tasks.json"):
        """
        初始化 Storage
        
        Args:
            file_path: JSON 檔案路徑
        """
        self.file_path = Path(file_path)
        self._ensure_file_exists()
    
    def _ensure_file_exists(self) -> None:
        """確保儲存檔案存在，若不存在則建立空檔案"""
        if not self.file_path.exists():
            # 確保目錄存在
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            # 建立空 JSON 檔案
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
    
    def load_tasks(self) -> List[Task]:
        """
        從 JSON 檔案載入所有任務
        
        Returns:
            Task 物件列表
        """
        if not self.file_path.exists():
            return []
        
        with open(self.file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        tasks = []
        for item in data:
            task = Task(
                id=item["id"],
                title=item["title"],
                priority=Priority[item["priority"]],
                status=TaskStatus(item["status"]),
                created_at=datetime.datetime.fromisoformat(item["created_at"])
            )
            tasks.append(task)
        
        return tasks
    
    def save_tasks(self, tasks: List[Task]) -> None:
        """
        將所有任務儲存到 JSON 檔案
        
        Args:
            tasks: Task 物件列表
        """
        # 確保目錄存在
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = []
        for task in tasks:
            data.append({
                "id": task.id,
                "title": task.title,
                "priority": task.priority.name,
                "status": task.status.value,
                "created_at": task.created_at.isoformat()
            })
        
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def append_task(self, task: Task) -> None:
        """
        新增單一任務到檔案
        
        Args:
            task: 要新增的 Task 物件
        """
        tasks = self.load_tasks()
        tasks.append(task)
        self.save_tasks(tasks)
    
    def update_task(self, task: Task) -> None:
        """
        更新現有任務
        
        Args:
            task: 更新後的 Task 物件
        """
        tasks = self.load_tasks()
        for i, t in enumerate(tasks):
            if t.id == task.id:
                tasks[i] = task
                break
        self.save_tasks(tasks)
    
    def delete_task_by_id(self, task_id: int) -> bool:
        """
        根據 ID 刪除任務
        
        Args:
            task_id: 要刪除的任務 ID
            
        Returns:
            若找到並刪除則返回 True，否則返回 False
        """
        tasks = self.load_tasks()
        original_len = len(tasks)
        tasks = [t for t in tasks if t.id != task_id]
        
        if len(tasks) < original_len:
            self.save_tasks(tasks)
            return True
        return False
