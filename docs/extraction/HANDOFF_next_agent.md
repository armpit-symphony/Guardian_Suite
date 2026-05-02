# LIMA Guardian Suite Fresh-Agent Handoff

Date: 2026-05-02
Repo: `https://github.com/armpit-symphony/LIMA-Guardian-Suite`
Start branch: `pr4k-sparkbot-lima-side-by-side-report`

## Branch and commits

Latest relevant commits:

- `49b08a7` `Fix Sparkbot Spine parity gaps in comparison stack`
- `d8bda87` `Add Sparkbot vs LIMA Spine side-by-side report`
- `f74f7e9` `Add Sparkbot Spine serializer fixture comparison`

## What is done

- PR 1: standalone `vault` + `auth`
- PR 2: standalone `policy` + `pending_approvals`
- PR 3: standalone `token_guardian` + `verifier` + `improvement`
- PR 4 / 4A / 4B / 4C: Spine planning, interfaces, events/producers, generic SQLite store
- PR 4D: Sparkbot adapter shim design doc
- PR 4E: read-only compatibility probe
- PR 4F: row-to-LIMA translation parity harness
- PR 4G: read-only Sparkbot adapter prototype
- PR 4H: route-shape parity checks
- PR 4I: field-level parity checks
- PR 4J: serializer fixture comparison
- PR 4K: side-by-side report
- Phase 5 parity fixes are saved on top of PR 4K

## Current state

- No Sparkbot runtime integration
- No Sparkbot source modifications
- No live DB migration
- No dual-write
- Everything remains copied-data-only / test-only for Spine comparison

## Important files

- `tools/spine_compatibility_probe.py`
- `tools/spine_translation_parity.py`
- `tools/spine_readonly_adapter_prototype.py`
- `tools/spine_route_shape_parity.py`
- `tools/spine_field_parity.py`
- `tools/spine_serializer_fixture_compare.py`
- `tools/spine_side_by_side_report.py`
- `docs/extraction/sparkbot_lima_side_by_side_report.md`

## Phase 5 fix scope

Added translators for:

- assignments
- approvals
- handoffs
- project_events

Updated the read-only adapter to derive:

- tasks
- projects
- relations

from event-only Sparkbot Spine data when task/project tables are empty.

Fixed parity resolution so route/field checks use real available room/task IDs instead of hard-coded `room-1` / `task-1`.

Fixed serializer parity normalization so copied real Sparkbot data can satisfy fixture shape checks without exposing raw payload details.

## Expected validation now

Focused parity suite:

```bash
pytest -q tests/test_spine_compatibility_probe.py tests/test_spine_translation_parity.py tests/test_spine_readonly_adapter_prototype.py tests/test_spine_route_shape_parity.py tests/test_spine_field_parity.py tests/test_spine_serializer_fixture_compare.py tests/test_spine_side_by_side_report.py
```

Result on the source machine: `55 passed, 1 warning`

## Known non-scope failures

Full `pytest -q` still fails in legacy areas:

- `app/services/guardian/meeting_recorder.py` needs `sqlmodel`
- legacy `guardian/vault.py` still has Python-2-style base64 behavior

These were intentionally not touched.

## Copied DB result on source machine

Source chosen:

- `/home/sparky/Sparkbot/data/guardian/spine.db`

Copied to:

- `/tmp/lima-spine-report-input/sparkbot_spine_copy.db`

Side-by-side report after Phase 5:

- `route_shape_pass = true`
- `field_level_pass = true`
- `serializer_fixture_pass = true`
- `overall_pass = true`

## Remaining known gap in report

- Producer translation is still derived from event subsystems rather than a persisted producer table

## Recommended next move

Do not integrate into Sparkbot yet.

Next safe step is another reporting/design PR or a persisted-producer parity improvement if needed.

If reproducing the side-by-side report on a new machine:

1. Copy a Sparkbot Spine DB to temp.
2. Run:

```bash
PYTHONPATH=/path/to/LIMA-Guardian-Suite python3 tools/spine_side_by_side_report.py \
  --source-db /tmp/your_spine_copy.db \
  --output-dir /tmp/lima-spine-side-by-side
```

## Fresh machine bootstrap

```bash
git clone https://github.com/armpit-symphony/LIMA-Guardian-Suite.git
cd LIMA-Guardian-Suite
git checkout pr4k-sparkbot-lima-side-by-side-report
pytest -q tests/test_spine_compatibility_probe.py tests/test_spine_translation_parity.py tests/test_spine_readonly_adapter_prototype.py tests/test_spine_route_shape_parity.py tests/test_spine_field_parity.py tests/test_spine_serializer_fixture_compare.py tests/test_spine_side_by_side_report.py
```
