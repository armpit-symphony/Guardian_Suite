"""
Memory Guardian - Secure memory operations and PII redaction.
"""

import re
import logging
from typing import List, Dict, Any

log = logging.getLogger(__name__)


# PII patterns for detection
PII_PATTERNS = {
    "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    "phone": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
    "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
    "credit_card": r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b',
    "api_key": r'\b(?:api[_-]?key|token)["\s:=]+[a-zA-Z0-9_-]{20,}\b',
}


class MemoryGuardian:
    """Secure memory operations and PII redaction."""
    
    def __init__(
        self,
        max_tokens: int = 100000,
        redact_pii: bool = True,
        preserve_context: bool = True,
    ):
        self.max_tokens = max_tokens
        self.redact_pii = redact_pii
        self.preserve_context = preserve_context
        self.context_history = []
        
    def build_context(self, messages: List[Dict]) -> List[Dict]:
        """Build context window from messages."""
        context = []
        total_tokens = 0
        
        # Build from most recent
        for msg in reversed(messages):
            content = msg.get("content", "")
            tokens = len(content.split())
            
            if total_tokens + tokens > self.max_tokens:
                break
                
            context.append(msg)
            total_tokens += tokens
            
        # Reverse to get chronological order
        context.reverse()
        
        self.context_history = context
        log.info(f"Memory Guardian: built context ({total_tokens} tokens)")
        
        return context
    
    def redact(self, messages: List[Dict]) -> List[Dict]:
        """Redact PII from messages."""
        if not self.redact_pii:
            return messages
            
        redacted = []
        for msg in messages:
            content = msg.get("content", "")
            
            # Apply each PII pattern
            for pii_type, pattern in PII_PATTERNS.items():
                content = re.sub(pattern, f"[{pii_type.upper()}_REDACTED]", content)
                
            redacted.append({**msg, "content": content})
            
        log.info(f"Memory Guardian: redacted {len(messages)} messages")
        return redacted
    
    def summarize(self, messages: List[Dict]) -> str:
        """Create a summary of conversation."""
        if not messages:
            return ""
            
        # Simple summary - just first and last
        first = messages[0].get("content", "")[:100]
        last = messages[-1].get("content", "")[:100]
        
        return f"Conversation: {len(messages)} messages. Started: {first}... Ended: {last}"
    
    def get_status(self) -> Dict:
        """Get memory guardian status."""
        return {
            "max_tokens": self.max_tokens,
            "redact_pii": self.redact_pii,
            "context_history_length": len(self.context_history)
        }
