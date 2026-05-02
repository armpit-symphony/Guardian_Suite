# Sparkbot Spine Translation Parity

Date: 2026-05-02
Status: Temp-copy-only parity harness
Target branch: `pr4f-spine-translation-parity-harness`

## Purpose

This harness translates copied Sparkbot Spine rows into LIMA Spine models and reports structural parity issues before any runtime adapter wiring starts.

It is meant to answer one narrow question:

Can the current Sparkbot Spine task, project, event, link, and producer-shaped data be translated into LIMA model instances without touching Sparkbot runtime?

## Safety model

- source DB path is treated as read-only
- the source DB is copied to a temp directory immediately
- all SQL reads happen against the temp copy only
- no route, dashboard, background job, or runtime import wiring changes occur
- the JSON report contains counts, field names, and flags only
- no raw payload values or secret-like strings are emitted

## Supported row translations

Current translation coverage:

- `guardian_spine_tasks` -> `SpineTask`
- `guardian_spine_projects` -> `SpineProject`
- `guardian_spine_events` -> `SpineEventEnvelope`
- `guardian_spine_links` -> `SpineRelation`
- distinct event subsystem rows -> derived `SpineProducer`

## Known limitations

- assignments are not translated yet
- approvals are not translated yet
- handoffs are not translated yet
- project events are not translated yet
- producer translation is derived from event rows, not a persisted producer table
- Sparkbot-only fields such as `created_by_subsystem`, `updated_by_subsystem`, `source_excerpt`, and `chat_task_id` are preserved as adapter metadata, not first-class LIMA fields

## Pass/fail criteria

The harness passes only if:

- the source DB exists
- temp copy succeeds
- task/project/event/link rows translate without failures
- the generated report writes successfully
- no raw secret-like values are emitted in the report

The harness may still pass while recording compatibility gaps, as long as those gaps are reported explicitly and do not break the supported translations.

## Next step after passing

The next safe PR after this is a Sparkbot-side read-only adapter prototype that consumes these translated LIMA models in parity tests only. No dual-write and no production route rewiring should happen before that parity layer is stable.
