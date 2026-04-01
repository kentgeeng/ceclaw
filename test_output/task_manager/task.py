"""
Task 模組 - 定義 Task 資料類別
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class Priority(Enum):
    """優先級列舉"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class TaskStatus(Enum):
    """任務狀態列舉"""
    PENDING = "待處理"
    IN_PROGRESS = "進行中"
    COMPLETED = "已完成"


@dataclass
class Task:
    """
    Task 資料類別
    
    Attributes:
        id: 任務唯一識別碼
        title: 任務標題
        priority: 優先級 (Priority 列舉)
        status: 任務狀態 (TaskStatus 列舉)
        created_at: 建立時間
    """
    id: int
    title: str
    priority: Priority
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    
    def __str__(self) -> str:
        """返回任務的可讀字串表示"""
        return f"[{self.id}] {self.title} | 優先級: {self.priority.name} | 狀態: {self.status.value}"
    
    def to_dict(self) -> dict:
        """將 Task 轉換為字典，用於 JSON 序列化"""
        return {
            "id": self.id,
            "title": self.title,
            "priority": self.priority.name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat()
        }
    
    @staticmethod
    def from_dict(data: dict) -> "Task":
        """從字典建立 Task 物件"""
        return Task(
            id=data["id"],
            title=data["title"],
            priority=Priority[data["priority"]],
            status=TaskStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"])
        )
