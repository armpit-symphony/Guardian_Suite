# Sparkbot Spine Compatibility Probe

Date: 2026-05-02
Status: Read-only probe only
Target branch: `pr4e-readonly-spine-compatibility-probe`

## Probe purpose

This probe compares the live Sparkbot Spine SQLite schema shape to the generic LIMA SpineStore shape using a copied temporary database only. It is not a migration tool and does not rewire Sparkbot runtime behavior.

The probe answers four narrow questions:

- does the copied Sparkbot DB contain the expected live Spine tables and migrated columns
- can the current Sparkbot task, project, event, and link tables be mapped to the generic LIMA store surface
- do event rows appear translatable into LIMA event categories without reading secrets back out
- do redaction markers remain present in sampled event payloads where sensitive keys exist

## Expected Sparkbot DB inputs

Expected input is a SQLite file that contains the Sparkbot Spine schema after `_ensure_schema_migrations()` has run.

Expected live tables:

- `guardian_spine_tasks`
- `guardian_spine_events`
- `guardian_spine_links`
- `guardian_spine_assignments`
- `guardian_spine_approvals`
- `guardian_spine_handoffs`
- `guardian_spine_projects`
- `guardian_spine_project_events`

The probe is intentionally read-only against the source path and will fail safely if the source DB is missing.

## Temp-copy safety rules

- never open the source DB for write
- immediately copy the source DB to a temp directory
- inspect the temp copy only
- emit a JSON report to a caller-provided output path
- never print raw row payloads, secret values, or excerpts to stdout/stderr
- only include aggregate counts, column names, and boolean flags in the report

## Schema comparison method

The probe compares three views of the database:

1. Actual Sparkbot schema from `sqlite_master` plus `PRAGMA table_info(...)`
2. Expected Sparkbot live schema contract
3. Expected LIMA generic store contract

Comparison output includes:

- missing Sparkbot tables
- missing Sparkbot columns by table
- extra columns by table
- generic LIMA tables that have a defined Sparkbot source mapping
- Sparkbot-only fields that still require adapter metadata or Sparkbot-owned side tables

## Event translation checks

The probe does not attempt a runtime migration. It only checks that event rows appear classifiable into LIMA event categories from:

- `event_type`
- `subsystem`
- `task_id`
- `project_id`

The report records:

- sampled event count
- invalid JSON payload count
- derived category counts
- number of rows with sensitive keys
- number of rows already carrying `[REDACTED]` markers

## Task/project parity checks

The probe checks that Sparkbot live tables expose the minimum columns needed to populate:

- LIMA `spine_tasks`
- LIMA `spine_projects`
- LIMA `spine_events`
- LIMA `spine_relations`

It also identifies fields that remain Sparkbot-specific and therefore must stay in adapter metadata or Sparkbot-owned tables during shim phases.

## Redaction checks

Redaction validation is aggregate-only.

The probe:

- scans sampled JSON payloads for secret-like keys such as `password`, `token`, `api_key`, and `secret`
- counts redacted markers
- counts suspicious secret-key hits
- never writes key values or payload text into the report

This keeps the probe safe to run on copied data while still detecting redaction regressions.

## Pass/fail criteria

The probe passes only if all of the following are true:

- source DB exists
- temp copy succeeds
- required Sparkbot live tables are present
- required migrated task, event, and project columns are present
- generic LIMA table mappings are defined for tasks, events, projects, and links
- no unsafe raw secret values are emitted by the probe itself

The probe may still report compatibility gaps while finishing successfully. Gaps are surfaced in the JSON report under mismatches and adapter-owned fields.

## Rollback / no-op guarantee

This probe is operationally a no-op against Sparkbot runtime:

- no Sparkbot imports
- no route changes
- no dashboard changes
- no dual-write
- no migration writes
- no changes to the source DB

If the probe fails, the only artifact is the requested JSON report path if it was written before failure handling completed.
