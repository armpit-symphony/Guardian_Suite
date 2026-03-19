"""Tests for Guardian Suite."""

import pytest
from guardian import (
    TokenGuardian,
    MemoryGuardian,
    ExecutiveGuardian,
    TaskGuardian,
    Vault,
    GuardianSuite
)


class TestTokenGuardian:
    def test_initialization(self):
        tg = TokenGuardian()
        assert tg.shadow_mode is True
        assert tg.total_spent == 0.0
        
    def test_route_simple_query(self):
        tg = TokenGuardian()
        messages = [{"content": "Hello"}]
        model, decision = tg.route("gpt-4", messages)
        assert decision.reason == "simple query - cost optimization"
        
    def test_record_usage(self):
        tg = TokenGuardian()
        tg.record_usage("gpt-4", 100, 50)
        assert tg.session_spent > 0
        
    def test_get_cost_report(self):
        tg = TokenGuardian()
        report = tg.get_cost_report()
        assert "total_spent" in report
        assert report["shadow_mode"] is True


class TestMemoryGuardian:
    def test_initialization(self):
        mg = MemoryGuardian()
        assert mg.redact_pii is True
        
    def test_build_context(self):
        mg = MemoryGuardian(max_tokens=1000)
        messages = [
            {"content": "Hello"},
            {"content": "How are you?"},
            {"content": "Goodbye"}
        ]
        context = mg.build_context(messages)
        assert len(context) <= 3
        
    def test_redact(self):
        mg = MemoryGuardian()
        messages = [{"content": "My email is test@example.com"}]
        redacted = mg.redact(messages)
        assert "[EMAIL_REDACTED]" in redacted[0]["content"]


class TestExecutiveGuardian:
    def test_initialization(self):
        eg = ExecutiveGuardian()
        assert eg.require_approval is True
        
    def test_allow_low_risk(self):
        eg = ExecutiveGuardian(require_approval=False)
        decision = eg.evaluate("read_file", {"path": "/tmp/test"})
        assert decision.action == "allow"
        
    def test_deny_high_risk(self):
        eg = ExecutiveGuardian(require_approval=True)
        decision = eg.evaluate("send_email", {"to": "test@example.com"})
        assert decision.action == "deny"


class TestTaskGuardian:
    def test_initialization(self):
        tg = TaskGuardian()
        assert tg.max_concurrent == 5
        
    def test_schedule(self):
        tg = TaskGuardian()
        
        async def dummy():
            return "done"
            
        task_id = tg.schedule("test", dummy, interval_seconds=60)
        assert task_id in tg.tasks


class TestVault:
    def test_initialization(self, tmp_path):
        vault = Vault(db_path=str(tmp_path / "vault.db"))
        assert vault.db_path.exists()
        
    def test_put_and_get(self, tmp_path):
        vault = Vault(db_path=str(tmp_path / "vault.db"))
        
        vault.put("test_key", "secret_value", policy="use_only")
        value = vault.get("test_key")
        
        assert value == "secret_value"
        
    def test_get_metadata(self, tmp_path):
        vault = Vault(db_path=str(tmp_path / "vault.db"))
        
        vault.put("test_key", "secret", category="api")
        meta = vault.get_metadata("test_key")
        
        assert meta["alias"] == "test_key"
        assert meta["category"] == "api"


class TestGuardianSuite:
    def test_initialization(self):
        suite = GuardianSuite(mode="personal")
        assert suite.mode == "personal"
        
    def test_get_status(self):
        suite = GuardianSuite(mode="office")
        status = suite.get_status()
        
        assert status["mode"] == "office"
        assert status["token"] == "active"
        assert status["executive"] == "active"  # office mode
