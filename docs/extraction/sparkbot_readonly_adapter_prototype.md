# Sparkbot Read-Only Adapter Prototype

Date: 2026-05-02
Status: Test-only prototype
Target branch: `pr4g-readonly-sparkbot-adapter-prototype`

## Purpose

This prototype exercises a Sparkbot-shaped read adapter over translated LIMA models without changing Sparkbot runtime wiring.

It validates that the temp-copy translation work from PR 4F is sufficient to support a narrow read-only surface:

- open queue
- blocked queue
- approval-waiting queue
- recent event feed
- room overview
- project workload summary
- task detail with dependency lineage

## Safety model

- source DB is treated as read-only
- the source DB is copied to a temp directory immediately
- only the temp copy is queried
- no write methods exist
- no Sparkbot imports are used
- no route, dashboard, or background job wiring changes are made

## Supported prototype surface

Current supported methods:

- `from_source_db()`
- `list_open_queue()`
- `list_blocked_queue()`
- `list_approval_waiting_queue()`
- `list_recent_events()`
- `get_room_overview()`
- `get_project_workload_summary()`
- `get_task_detail()`

The adapter returns translated LIMA model objects or simple derived dictionaries. It does not attempt to recreate the full Sparkbot route layer.

## Known limitations

- approvals remain empty in task detail
- handoffs remain empty in task detail
- no project-event view yet
- no assignment history view yet
- queue heuristics are intentionally narrow and should not be treated as runtime parity proof

## Pass criteria

The prototype is considered useful only if:

- it always uses a temp copy
- event payloads remain redacted
- queue reads match the sample fixtures
- room overview and project workload can be derived without Sparkbot imports

## Next step

The next safe PR after this is a test-only parity layer that compares selected Sparkbot route response shapes to adapter-produced read models on copied data. Runtime rewiring should still remain out of scope.
