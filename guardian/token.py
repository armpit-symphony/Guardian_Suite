"""
Token Guardian - Monitor and optimize token usage.
"""

import os
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class RouteDecision:
    model: str
    provider: str
    reason: str
    confidence: float
    estimated_cost: float = 0.0


class TokenGuardian:
    """Token usage tracking and model routing."""
    
    # Default model costs (per 1K tokens)
    DEFAULT_COSTS = {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.001, "output": 0.002},
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.0012},
        "gemini-pro": {"input": 0.00125, "output": 0.005},
    }
    
    def __init__(
        self,
        shadow_mode: bool = True,
        model_routing: bool = True,
        cost_tracking: bool = True,
        max_cost_per_hour: float = 10.0,
    ):
        self.shadow_mode = shadow_mode or os.getenv("TOKEN_GUARDIAN_SHADOW", "true").lower() == "true"
        self.model_routing = model_routing
        self.cost_tracking = cost_tracking
        self.max_cost_per_hour = max_cost_per_hour
        
        self.total_spent = 0.0
        self.session_spent = 0.0
        self.usage_history = []
        
    def route(self, default_model: str, messages: list) -> Tuple[str, RouteDecision]:
        """Route to best model based on query complexity."""
        if not self.model_routing:
            return default_model, RouteDecision(
                model=default_model,
                provider="default",
                reason="routing disabled",
                confidence=1.0
            )
        
        # Simple routing logic
        total_tokens = sum(len(m.get("content", "").split()) for m in messages)
        
        # Route simple queries to cheaper models
        if total_tokens < 100:
            model = "gpt-3.5-turbo"
            reason = "simple query - cost optimization"
            confidence = 0.8
        elif total_tokens < 1000:
            model = "gpt-4-turbo"
            reason = "medium complexity"
            confidence = 0.7
        else:
            model = default_model
            reason = "high complexity - full model"
            confidence = 0.6
            
        # Check cost budget
        if self.session_spent >= self.max_cost_per_hour:
            model = "gpt-3.5-turbo"
            reason = "budget limit reached"
            confidence = 0.9
            
        decision = RouteDecision(
            model=model,
            provider="openai",
            reason=reason,
            confidence=confidence,
            estimated_cost=self._estimate_cost(model, total_tokens)
        )
        
        log.info(f"Token Guardian: routed to {model} ({reason})")
        
        if self.shadow_mode and model != default_model:
            # In shadow mode, return default but log the decision
            return default_model, decision
            
        return model, decision
    
    def record_usage(self, model: str, input_tokens: int, output_tokens: int):
        """Record actual token usage."""
        if not self.cost_tracking:
            return
            
        cost = self._calculate_cost(model, input_tokens, output_tokens)
        self.total_spent += cost
        self.session_spent += cost
        
        self.usage_history.append({
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost
        })
        
        log.info(f"Token Guardian: recorded ${cost:.4f} for {model}")
        
    def record_tool_usage(self, tool_name: str, result: any):
        """Record tool execution for tracking."""
        # Simplified - just log for now
        log.debug(f"Token Guardian: tool {tool_name} executed")
        
    def get_cost_report(self) -> Dict:
        """Get current cost report."""
        return {
            "total_spent": round(self.total_spent, 4),
            "session_spent": round(self.session_spent, 4),
            "max_budget": self.max_cost_per_hour,
            "shadow_mode": self.shadow_mode,
            "usage_count": len(self.usage_history)
        }
        
    def _estimate_cost(self, model: str, tokens: int) -> float:
        """Estimate cost for token count."""
        costs = self.DEFAULT_COSTS.get(model, {"input": 0.01, "output": 0.01})
        return (tokens / 1000) * costs["input"]
        
    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate actual cost."""
        costs = self.DEFAULT_COSTS.get(model, {"input": 0.01, "output": 0.01})
        return (input_tokens / 1000) * costs["input"] + (output_tokens / 1000) * costs["output"]
