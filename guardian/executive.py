"""
Executive Guardian - High-risk action approval gates and decision journaling.
"""

import json
import logging
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

log = logging.getLogger(__name__)


@dataclass
class Decision:
    action: str  # "allow", "deny", "privileged", "privileged_reveal"
    reason: str
    tool_name: str
    tool_args: Dict
    timestamp: str
    high_risk: bool = False


class ExecutiveGuardian:
    """High-risk action approval gates and decision journaling."""
    
    # Default high-risk tools
    DEFAULT_HIGH_RISK = {
        "send_email", "execute_shell", "write_file", "delete_file",
        "execute_code", "send_message", "post_to_social",
        "make_payment", "access_credentials", "modify_config"
    }
    
    def __init__(
        self,
        require_approval: bool = True,
        high_risk_tools: Optional[set] = None,
        journal_path: str = "data/guardian/executive/decisions/",
    ):
        self.require_approval = require_approval
        self.high_risk_tools = high_risk_tools or self.DEFAULT_HIGH_RISK
        self.journal_path = journal_path
        self.decisions = []
        
        # Ensure journal directory exists
        os.makedirs(journal_path, exist_ok=True)
        
    def evaluate(self, tool_name: str, tool_args: Dict) -> Decision:
        """Evaluate if tool should be allowed."""
        is_high_risk = tool_name in self.high_risk_tools
        timestamp = datetime.utcnow().isoformat()
        
        if not self.require_approval:
            decision = Decision(
                action="allow",
                reason="approval disabled",
                tool_name=tool_name,
                tool_args=tool_args,
                timestamp=timestamp,
                high_risk=is_high_risk
            )
            self._journal(decision)
            return decision
            
        if is_high_risk:
            # High risk - require approval or deny
            decision = Decision(
                action="deny",
                reason=f"High-risk tool '{tool_name}' requires approval",
                tool_name=tool_name,
                tool_args=tool_args,
                timestamp=timestamp,
                high_risk=True
            )
            log.warning(f"Executive Guardian: denied {tool_name} (high risk)")
        else:
            decision = Decision(
                action="allow",
                reason="low risk tool",
                tool_name=tool_name,
                tool_args=tool_args,
                timestamp=timestamp,
                high_risk=False
            )
            
        self._journal(decision)
        return decision
    
    def _journal(self, decision: Decision):
        """Journal decision to disk."""
        self.decisions.append(decision)
        
        # Write to journal file
        journal_file = os.path.join(
            self.journal_path,
            f"decision_{decision.timestamp.replace(':', '-')}.json"
        )
        
        try:
            with open(journal_file, 'w') as f:
                json.dump(asdict(decision), f, indent=2)
        except Exception as e:
            log.error(f"Failed to journal decision: {e}")
            
    def journal(self, decision: Decision):
        """Public method to journal a decision."""
        self._journal(decision)
        
    def get_recent_decisions(self, limit: int = 10) -> list:
        """Get recent decisions."""
        return self.decisions[-limit:]
    
    def get_status(self) -> Dict:
        """Get executive guardian status."""
        return {
            "require_approval": self.require_approval,
            "high_risk_tools_count": len(self.high_risk_tools),
            "decisions_made": len(self.decisions),
            "journal_path": self.journal_path
        }
