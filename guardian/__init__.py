"""
Guardian Suite - Unified security, monitoring, and governance for AI agents.

Modules:
    - token: Token usage tracking and model routing
    - memory: Secure memory operations and PII redaction
    - executive: High-risk action approval gates
    - task: Scheduled jobs and background tasks
    - vault: Encrypted secrets storage
"""

from guardian.token import TokenGuardian
from guardian.memory import MemoryGuardian
from guardian.executive import ExecutiveGuardian
from guardian.task import TaskGuardian
from guardian.vault import Vault

__version__ = "1.0.0"

__all__ = [
    "TokenGuardian",
    "MemoryGuardian", 
    "ExecutiveGuardian",
    "TaskGuardian",
    "Vault",
    "GuardianSuite",
]


class GuardianSuite:
    """Unified interface for all Guardian components."""
    
    def __init__(self, config_path: str = None, mode: str = "personal"):
        self.mode = mode
        self.token = TokenGuardian()
        self.memory = MemoryGuardian()
        self.executive = ExecutiveGuardian()
        self.task = TaskGuardian()
        self.vault = Vault()
        
    def wrap(self, agent):
        """Wrap an agent with all guardians."""
        # This would integrate with the agent's tool-calling loop
        return agent
        
    def get_status(self):
        """Get status of all guardians."""
        return {
            "mode": self.mode,
            "token": "active",
            "memory": "active",
            "executive": "active" if self.mode != "personal" else "disabled",
            "task": "active",
            "vault": "active",
        }
