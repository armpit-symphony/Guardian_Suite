"""
Task Guardian - Scheduled jobs, background tasks, and follow-up management.
"""

import asyncio
import logging
import uuid
from typing import Dict, Callable, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

log = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    task_id: str
    name: str
    func: Callable
    schedule: str  # cron-like or interval
    enabled: bool
    last_run: Optional[str]
    next_run: Optional[str]


class TaskGuardian:
    """Scheduled jobs and background task management."""
    
    def __init__(
        self,
        max_concurrent: int = 5,
        default_interval: int = 300,  # 5 minutes
    ):
        self.max_concurrent = max_concurrent
        self.default_interval = default_interval
        self.tasks: Dict[str, ScheduledTask] = {}
        self.results: Dict[str, Any] = {}
        self.running_tasks: int = 0
        
    def schedule(
        self,
        name: str,
        func: Callable,
        interval_seconds: Optional[int] = None,
        cron: Optional[str] = None,
    ) -> str:
        """Schedule a task for recurring execution."""
        task_id = str(uuid.uuid4())[:8]
        
        interval = interval_seconds or self.default_interval
        next_run = datetime.utcnow() + timedelta(seconds=interval)
        
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            func=func,
            schedule=cron or f"every {interval}s",
            enabled=True,
            last_run=None,
            next_run=next_run.isoformat()
        )
        
        self.tasks[task_id] = task
        log.info(f"Task Guardian: scheduled {name} ({task_id})")
        
        return task_id
    
    async def run(self, task_id: str, *args, **kwargs) -> Any:
        """Run a scheduled task now."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")
            
        if self.running_tasks >= self.max_concurrent:
            raise RuntimeError("Max concurrent tasks reached")
            
        task = self.tasks[task_id]
        
        self.running_tasks += 1
        try:
            result = await task.func(*args, **kwargs)
            task.last_run = datetime.utcnow().isoformat()
            self.results[task_id] = {"status": "success", "result": result}
            log.info(f"Task Guardian: {task.name} completed")
            return result
        except Exception as e:
            self.results[task_id] = {"status": "error", "error": str(e)}
            log.error(f"Task Guardian: {task.name} failed: {e}")
            raise
        finally:
            self.running_tasks -= 1
            
    def cancel(self, task_id: str) -> bool:
        """Cancel a scheduled task."""
        if task_id in self.tasks:
            self.tasks[task_id].enabled = False
            log.info(f"Task Guardian: cancelled {task_id}")
            return True
        return False
    
    def list_tasks(self) -> list:
        """List all scheduled tasks."""
        return [
            {
                "task_id": t.task_id,
                "name": t.name,
                "schedule": t.schedule,
                "enabled": t.enabled,
                "last_run": t.last_run,
                "next_run": t.next_run
            }
            for t in self.tasks.values()
        ]
    
    def get_status(self) -> Dict:
        """Get task guardian status."""
        return {
            "total_tasks": len(self.tasks),
            "enabled_tasks": sum(1 for t in self.tasks.values() if t.enabled),
            "running_tasks": self.running_tasks,
            "max_concurrent": self.max_concurrent,
            "results_cached": len(self.results)
        }
