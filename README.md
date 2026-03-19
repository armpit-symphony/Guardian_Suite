# Guardian Suite

**Unified security, monitoring, and governance layer for AI agents.**

Guardian Suite provides a comprehensive set of tools to secure, monitor, and govern AI agent operations. Designed to work with OpenClaw, Hermes, or any Python-based AI agent framework.

---

## Features

| Guardian | Purpose |
|----------|---------|
| **Token Guardian** | Monitor and optimize token usage, model routing, cost tracking |
| **Memory Guardian** | Secure memory operations, PII redaction, context management |
| **Executive Guardian** | High-risk action approval gates, decision journaling |
| **Task Guardian** | Scheduled jobs, background tasks, follow-up management |
| **Vault** | Encrypted secrets storage for API keys and credentials |

---

## Installation

```bash
# Clone the repo
git clone https://github.com/armpit-symphony/Guardian_Suite.git
cd Guardian_Suite

# Install dependencies
pip install -e .

# Or with specific features
pip install -e ".[openclaw]"    # OpenClaw adapter
pip install -e ".[all]"          # All adapters
```

---

## Quick Start

### 1. Basic Usage

```python
from guardian import GuardianSuite

# Initialize
guardians = GuardianSuite()

# Wrap your agent
agent = guardians.wrap(agent)

# Now your agent has:
# - Token tracking and optimization
# - Memory安全管理
# - High-risk action approval gates
# - Task scheduling
# - Secrets vault
```

### 2. OpenClaw Adapter

```python
from guardian.adapters.openclaw import OpenClawGuardian

guardian = OpenClawGuardian(
    config_path="config/guardian.yaml"
)

# Integrate with OpenClaw agent scope
guardian.register()
```

### 3. Standalone Token Guardian

```python
from guardian.token import TokenGuardian

tg = TokenGuardian(
    model_routing=True,
    cost_tracking=True,
    shadow_mode=True  # Test before going live
)

# Use as middleware
response = tg.route(model, messages)
```

---

## Configuration

Create `config/guardian.yaml`:

```yaml
token_guardian:
  enabled: true
  shadow_mode: true
  models:
    - provider: openai
      model: gpt-4
      cost_per_1k_input: 0.03
      cost_per_1k_output: 0.06

memory_guardian:
  enabled: true
  max_context_tokens: 100000
  redact_pii: true

executive_guardian:
  enabled: true
  high_risk_tools:
    - send_email
    - execute_shell
    - write_file
  require_approval: true

task_guardian:
  enabled: true
  max_concurrent: 5

vault:
  enabled: true
  key_path: .guardian/vault.key
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GUARDIAN_MODE` | `personal`, `office`, or `security` |
| `SPARKBOT_VAULT_KEY` | Encryption key for vault |
| `OPENCLAW_SESSIONS_DIR` | Path to OpenClaw sessions |
| `TOKEN_GUARDIAN_SHADOW` | Enable shadow mode |

---

## Mode: Personal vs Office vs Security

| Mode | Token Guardian | Memory Guardian | Executive Guardian | Task Guardian |
|------|---------------|-----------------|-------------------|---------------|
| **Personal** | Basic | Basic | Off | On |
| **Office** | Full | Full | Approval gates | Full |
| **Security** | Full + audit | Full + PII | Strict gates | Restricted |

Set via `GUARDIAN_MODE` env var.

---

## API Reference

### TokenGuardian

```python
from guardian.token import TokenGuardian

tg = TokenGuardian()

# Route to best model
model, metadata = tg.route(base_model, messages)

# Track usage
tg.record_usage(model, input_tokens, output_tokens)

# Get cost report
report = tg.get_cost_report()
```

### MemoryGuardian

```python
from guardian.memory import MemoryGuardian

mg = MemoryGuardian(max_tokens=100000)

# Build context
context = mg.build_context(messages)

# Redact PII
clean = mg.redact(messages)
```

### ExecutiveGuardian

```python
from guardian.executive import ExecutiveGuardian

eg = ExecutiveGuardian()

# Check if approval needed
decision = eg.evaluate(tool_name, tool_args)

# Journal decision
eg.journal(decision)
```

### TaskGuardian

```python
from guardian.task import TaskGuardian

tg = TaskGuardian()

# Schedule task
task_id = tg.schedule("0 9 * * *", my_function)

# Run now
result = tg.run(task_id)
```

### Vault

```python
from guardian.vault import Vault

vault = Vault()

# Store secret
vault.put("api_key", "secret-value", policy="use_only")

# Retrieve (internal use only)
value = vault.get("api_key")
```

---

## Testing

```bash
# Run all tests
pytest tests/

# Run specific guardian
pytest tests/test_token_guardian.py

# With coverage
pytest --cov=guardian tests/
```

---

## Integration Examples

### OpenClaw

```python
# In your agent scope
from guardian.adapters.openclaw import OpenClawGuardian

guardian = OpenClawGuardian()
await guardian.register()

# Tools now wrapped
```

### Hermes Bot

```python
# In your Hermes setup
from guardian.adapters.hermes import HermesGuardian

guardian = HermesGuardian(config)
hermes.use_middleware(guardian)
```

### Custom Agent

```python
# Wrap any Python agent
from guardian.adapters.base import GuardianMiddleware

class MyAgent:
    pass

agent = GuardianMiddleware(MyAgent())
```

---

## License

MIT

---

## Support

- Documentation: [docs.guadiansuite.io](https://docs.guadiansuite.io)
- Issues: [github.com/armpit-symphony/Guardian_Suite/issues](https://github.com/armpit-symphony/Guardian_Suite/issues)
