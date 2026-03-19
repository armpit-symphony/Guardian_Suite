"""
OpenClaw adapter for Guardian Suite.
"""

import os
from typing import Optional


class OpenClawGuardian:
    """Adapter for integrating Guardian Suite with OpenClaw."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config/guardian.yaml"
        self.mode = os.getenv("GUARDIAN_MODE", "personal")
        
    async def register(self):
        """Register guardians with OpenClaw agent scope."""
        from guardian import (
            TokenGuardian, 
            MemoryGuardian, 
            ExecutiveGuardian,
            TaskGuardian,
            Vault
        )
        
        # Initialize all guardians
        self.token_guardian = TokenGuardian()
        self.memory_guardian = MemoryGuardian()
        self.executive_guardian = ExecutiveGuardian()
        self.task_guardian = TaskGuardian()
        self.vault = Vault()
        
        print(f"Guardian Suite registered with OpenClaw (mode: {self.mode})")
        
    def wrap_tool(self, tool_name: str, tool_func):
        """Wrap a tool with guardian checks."""
        async def wrapped(*args, **kwargs):
            # Check executive guardian for high-risk tools
            if self.mode != "personal":
                decision = self.executive_guardian.evaluate(tool_name, kwargs)
                if decision.action == "deny":
                    return {"error": f"POLICY DENIED: {decision.reason}"}
                if decision.action == "privileged":
                    return {"error": "PRIVILEGED: Approval required"}
            
            # Execute tool
            result = await tool_func(*args, **kwargs)
            
            # Record token usage if applicable
            if hasattr(self, 'token_guardian'):
                self.token_guardian.record_tool_usage(tool_name, result)
                
            return result
            
        return wrapped
    
    def get_status(self):
        """Get guardian status for OpenClaw observability."""
        return {
            "guardian_suite": "active",
            "mode": self.mode,
            "components": {
                "token": hasattr(self, 'token_guardian'),
                "memory": hasattr(self, 'memory_guardian'),
                "executive": hasattr(self, 'executive_guardian'),
                "task": hasattr(self, 'task_guardian'),
                "vault": hasattr(self, 'vault'),
            }
        }
