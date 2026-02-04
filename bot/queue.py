"""Task queue for report generation"""
import asyncio
import uuid
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ReportTask:
    """Task for report generation"""
    task_id: str
    user_id: int
    chat_id: int
    articles: list[int]
    loading_message_id: Optional[int] = None
    
    @classmethod
    def create(cls, user_id: int, chat_id: int, articles: list[int], loading_message_id: Optional[int] = None):
        """Create new task with unique ID"""
        return cls(
            task_id=str(uuid.uuid4()),
            user_id=user_id,
            chat_id=chat_id,
            articles=articles,
            loading_message_id=loading_message_id
        )


@dataclass
class ReportResult:
    """Result of report generation"""
    task_id: str
    user_id: int
    chat_id: int
    success: bool
    file_path: Optional[str] = None
    error: Optional[str] = None
    loading_message_id: Optional[int] = None


class ReportQueue:
    """Async queue for report tasks"""
    
    def __init__(self, maxsize: int = 0):
        """
        Initialize queue
        
        Args:
            maxsize: Maximum queue size (0 = unlimited)
        """
        self._task_queue: asyncio.Queue[ReportTask] = asyncio.Queue(maxsize=maxsize)
        self._result_queue: asyncio.Queue[ReportResult] = asyncio.Queue()
        logger.info(f"✅ Report queue initialized (maxsize={maxsize if maxsize > 0 else 'unlimited'})")
    
    async def add_task(self, task: ReportTask):
        """Add task to queue"""
        await self._task_queue.put(task)
        logger.info(f"📥 Task added to queue: {task.task_id}")
    
    async def get_task(self) -> ReportTask:
        """Get task from queue (blocking)"""
        return await self._task_queue.get()
    
    async def add_result(self, result: ReportResult):
        """Add result to result queue"""
        await self._result_queue.put(result)
        logger.info(f"📤 Result added: {result.task_id} (success: {result.success})")
    
    async def get_result(self) -> ReportResult:
        """Get result from result queue (blocking)"""
        return await self._result_queue.get()
    
    def task_done(self):
        """Mark task as done"""
        self._task_queue.task_done()
    
    def qsize(self) -> int:
        """Get current queue size"""
        return self._task_queue.qsize()
    
    def empty(self) -> bool:
        """Check if queue is empty"""
        return self._task_queue.empty()
