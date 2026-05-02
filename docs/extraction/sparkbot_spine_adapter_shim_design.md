# Sparkbot Spine Adapter Shim Design

Date: 2026-05-02
Status: Design only
Source of truth: Sparkbot `backend/app/services/guardian/spine.py` remains canonical
Target branch: `pr4d-sparkbot-spine-adapter-shim-design`

## 1. Current Sparkbot Spine call sites

Sparkbot does not use Spine as a narrow storage library. It uses Spine as a combined event ingester, canonical task/project catalog, queue engine, ORM mirror, and operator API backing store. The adapter shim therefore has to intercept multiple categories of usage without changing behavior.

### Core runtime module

- `backend/app/services/guardian/spine.py`
  Owns the live SQLite schema, `_ensure_schema_migrations()`, producer registry, event ingestion, queue derivation, project mutations, chat-task sync, and dashboard read models.

### ORM and intake call sites

- `backend/app/crud.py:211`
  Emits room lifecycle events.
- `backend/app/crud.py:324-334`
  Calls `capture_message()` and `emit_worker_status_event()` during message creation flows.
- `backend/app/crud.py:493-504`
  Calls `capture_meeting_artifact()` and `emit_meeting_output_event()`.

### Guardian producer call sites

- `backend/app/services/guardian/pending_approvals.py:110,153,204`
  Calls `emit_approval_event()`.
- `backend/app/services/guardian/vault.py:29-35`
  Calls `ingest_subsystem_event()` for vault audit events.
- `backend/app/services/guardian/token_guardian.py:224-230`
  Calls `ingest_subsystem_event()` for routing telemetry.
- `backend/app/services/guardian/memory.py:898-899`
  Calls `ingest_subsystem_event()` for memory resurfacing.
- `backend/app/services/guardian/improvement.py:529-534`
  Calls `ingest_subsystem_event()` for improvement proposals.
- `backend/app/services/guardian/executive.py:81,116`
  Calls `ingest_executive_decision()`.
- `backend/app/services/guardian/task_guardian.py:714`
  Calls `ingest_task_guardian_result()`.

### Sparkbot execution adapters

- `backend/app/services/guardian/task_master_adapter.py`
  Reads queue views via `get_task_master_overview()`, `list_open_queue()`, `list_blocked_queue()`, `list_stale_tasks()`, and related helpers.
  Writes task lifecycle events via `sync_chat_task_created()` and `emit_task_master_action()`.
- `backend/app/services/guardian/project_executive.py`
  Treats Spine as canonical project state and mutates it through `emit_project_lifecycle_event()`, `update_project_metadata()`, `update_project_owner()`, `update_project_status_canonical()`, `attach_task_to_project_canonical()`, and `detach_task_from_project_canonical()`.

### API and dashboard call sites

- `backend/app/api/routes/chat/spine.py`
  Exposes room and operator endpoints backed directly by Spine dataclasses and queue/project readers.
- `frontend/src/lib/spine.ts`
  Hard-codes the operator API response contracts.
- `frontend/src/routes/_layout/spine.tsx`
  Assumes current queue names, counts, and task/project/event fields.

### Test coverage acting as compatibility contract

- `backend/tests/services/test_guardian_spine.py`
- `backend/tests/services/test_project_executive.py`

These tests are the current executable specification for the future shim.

## 2. Exact adapter seams needed

The existing LIMA `spine_interfaces.py` contracts are the right base, but Sparkbot needs a shim layer that composes them into Sparkbot-shaped entrypoints.

### Seam A: `SparkbotSpineRuntime`

Purpose:
Provide a module-local facade inside Sparkbot that preserves the current `spine.py` public API while delegating selected work to LIMA components.

Required responsibilities:

- hold a `SQLiteSpineStore` instance or future compatible LIMA store
- expose Sparkbot-compatible functions such as `ingest_subsystem_event()` and queue readers
- preserve current return shapes for Sparkbot callers
- keep Sparkbot-only behavior local to the shim

### Seam B: `SparkbotChatTaskMirrorAdapter`

Purpose:
Own all `ChatTask` and SQLModel coupling that cannot live in `lima_guardian`.

Required methods:

- `sync_chat_task_created(session, task)`
- `sync_chat_task_status(session, task, status)`
- `get_spine_task_by_chat_task_id(chat_task_id)`
- `mirror_spine_task_to_chat_task(session, spine_task)`

Sparkbot-specific behavior:

- `ChatTask`, `ChatRoom`, `ChatMeetingArtifact`, `Session`
- `TaskStatus` mapping
- `chat_task_id` persistence

### Seam C: `SparkbotProjectMirrorAdapter`

Purpose:
Own markdown/project mirror side effects and project-room conventions.

Required methods:

- `project_from_room(room_name)`
- `write_project_mirror(project)`
- `write_handoff_mirror(handoff)`
- `derive_default_project(room_id, room_name)`

Sparkbot-specific behavior:

- mirror file layout
- room-derived project naming

### Seam D: `SparkbotApprovalMirrorAdapter`

Purpose:
Bridge the generic approval state in LIMA with Sparkbot’s `pending_approvals.py` queue and breakglass UX.

Required methods:

- `mirror_pending_approval(confirm_id, state, task_id, payload)`
- `find_target_task(room_id, tool_name, event_type)`
- `expire_pending(confirm_id)`

Sparkbot-specific behavior:

- confirm-id lookup
- approval target inference
- breakglass route coordination

### Seam E: `SparkbotDashboardQueryAdapter`

Purpose:
Preserve the current operator API and frontend contract even if LIMA store internals differ.

Required methods:

- `get_room_overview(room_id)`
- `get_task_master_overview(room_id, limit_per_queue)`
- `get_task_detail(task_id)`
- `get_project_workload_summary(room_id)`
- queue readers for operator endpoints

Sparkbot-specific behavior:

- response envelopes used by `frontend/src/lib/spine.ts`
- queue naming and count semantics

### Seam F: `SparkbotProducerRegistryAdapter`

Purpose:
Preserve Sparkbot’s current in-memory producer registry and descriptions while allowing LIMA store persistence later if needed.

Required methods:

- `register_spine_producer(registration)`
- `list_registered_spine_producers()`
- `seed_default_producers()`

Sparkbot-specific behavior:

- exact default subsystem names and descriptions
- producer list ordering expected by tests/UI

## 3. Mapping from Sparkbot live Spine schema to LIMA generic SpineStore schema

The current LIMA store models only five tables:

- `spine_events`
- `spine_tasks`
- `spine_projects`
- `spine_relations`
- `spine_producers`

Sparkbot live Spine currently owns eight tables plus migrated columns:

- `guardian_spine_tasks`
- `guardian_spine_events`
- `guardian_spine_links`
- `guardian_spine_assignments`
- `guardian_spine_approvals`
- `guardian_spine_handoffs`
- `guardian_spine_projects`
- `guardian_spine_project_events`

### Direct mappings

| Sparkbot live table/field | LIMA generic target | Notes |
| --- | --- | --- |
| `guardian_spine_tasks.task_id` | `spine_tasks.task_id` | Direct |
| `room_id`, `title`, `summary`, `project_id`, `type`, `priority`, `status`, `owner_kind`, `owner_id`, `approval_required`, `approval_state`, `confidence`, `parent_task_id`, `depends_on_json`, `tags_json`, `source_kind`, `source_ref`, `created_at`, `updated_at`, `last_progress_at`, `closed_at` | `spine_tasks` same-named fields | Direct or near-direct |
| `guardian_spine_events.event_id`, `event_type`, `occurred_at`, `room_id`, `subsystem`, `actor_kind`, `actor_id`, `source_kind`, `source_ref`, `correlation_id`, `task_id`, `project_id`, `payload_json` | `spine_events` | Direct, but LIMA also requires `category`, `metadata_json`, `created_at`, `updated_at` |
| `guardian_spine_projects.project_id`, `display_name`, `slug`, `room_id`, `summary`, `status`, `tags_json`, `parent_project_id`, `owner_kind`, `owner_id`, `created_at`, `updated_at` | `spine_projects` | Direct |
| `guardian_spine_links` | `spine_relations` | `task_id -> from_entity_id`, `related_task_id -> to_entity_id`, `link_type -> relation_type`, both entity types = `task` |
| in-memory producer registry | `spine_producers` | LIMA persists producers, Sparkbot currently does not |

### Sparkbot-only fields that must be preserved in adapter metadata

| Sparkbot field | LIMA location during shim phase | Why |
| --- | --- | --- |
| `guardian_spine_tasks.created_by_guardian` | `spine_tasks.metadata.created_by_guardian` | LIMA core does not model it directly |
| `created_by_subsystem` | `spine_tasks.metadata.created_by_subsystem` | Required by Sparkbot task responses |
| `updated_by_subsystem` | `spine_tasks.metadata.updated_by_subsystem` | Required by Sparkbot task responses |
| `source_excerpt` | `spine_tasks.metadata.source_excerpt` | Used for traceability/debugging |
| `chat_task_id` | `spine_tasks.metadata.chat_task_id` or adapter-local index | Sparkbot ORM mirror key |
| `guardian_spine_projects.source_kind` | `spine_projects.metadata.source_kind` | Required by project API |
| `source_ref` | `spine_projects.metadata.source_ref` | Required by project API |
| `created_by_subsystem` | `spine_projects.metadata.created_by_subsystem` | Required by project API |
| `updated_by_subsystem` | `spine_projects.metadata.updated_by_subsystem` | Required by project API |

### Live Sparkbot tables not yet represented in LIMA core

| Sparkbot live table | Shim treatment in first adapter phase | Risk |
| --- | --- | --- |
| `guardian_spine_assignments` | Keep Sparkbot-owned or synthesize from task owner transitions | Medium |
| `guardian_spine_approvals` | Keep Sparkbot-owned; mirror read model only | High |
| `guardian_spine_handoffs` | Keep Sparkbot-owned; optionally synthesize event links later | High |
| `guardian_spine_project_events` | Keep Sparkbot-owned until per-project event log lands in LIMA | High |

### Event category derivation required by the shim

Sparkbot events do not store a standalone category column. LIMA does.

The shim must derive `SpineEventType` from current Sparkbot data using:

- `subsystem`
- `event_type`
- `task_id`
- `project_id`

Initial derivation rules:

- approval and breakglass events -> `approval` or `security`
- executive decisions -> `executive` or `verifier` depending on source
- meeting outputs -> `meeting`
- project lifecycle -> `project`
- handoff events -> `handoff`
- worker status -> `worker`
- fallback -> `other`

This derivation belongs in the Sparkbot adapter, not in generic LIMA storage.

## 4. Read/write compatibility risks

### Risk 1: task reads lose Sparkbot-only fields

Impact:
Sparkbot routes and frontend currently expect `created_by_subsystem`, `updated_by_subsystem`, and `chat_task_id`.

Mitigation:
Keep those fields adapter-owned and materialize them from task metadata or side indexes before returning API objects.

### Risk 2: event reads change ordering or payload shape

Impact:
Dashboard views and tests assume JSON payloads stay parseable and event ordering remains stable.

Mitigation:
Preserve append ordering by `occurred_at`; keep payload JSON untouched; never normalize away existing payload keys.

### Risk 3: project reads lose per-project history

Impact:
`list_project_events()` and `list_project_handoffs()` currently read dedicated tables. LIMA core does not yet store those.

Mitigation:
Do not reroute those reads until LIMA adds equivalent project-event and handoff persistence.

### Risk 4: writes duplicate state across two stores

Impact:
If Sparkbot writes both `guardian_spine_*` and LIMA `spine_*` tables during the shim phase, drift becomes likely.

Mitigation:
The first prototype must be read-only or single-write with shadow comparison only. No dual-write in the first adapter PR.

### Risk 5: queue derivation changes

Impact:
Task Master and project workload views are driven by Sparkbot-specific queue heuristics.

Mitigation:
Keep queue derivation in Sparkbot until parity fixtures prove the LIMA read model matches current behavior.

## 5. Event redaction requirements

The adapter shim must preserve the security work completed in Sparkbot v1.6.48.

Required invariants:

- approval events must keep secret-like `tool_args` redacted before event emission
- executive events must keep metadata and excerpt redaction
- vault, breakglass, token, and memory events must not leak secrets into metadata or payload
- the shim must never reconstruct original secret values from Sparkbot stores
- dry-run migration tooling must validate redaction parity, not only row counts

Adapter rules:

- treat Sparkbot event payloads as already security-processed
- support an additional shim-side scrubber for migration validation reports
- do not log raw payload JSON during comparison failures

## 6. Background job duplication risks

The shim must not cause the same logical event to be emitted twice.

High-risk producers:

- `task_guardian_scheduler()` and task guardian run completion/blocking flows
- memory resurfacing and nightly hygiene flows
- room/message creation flows in `crud.py`
- meeting artifact capture

Failure modes:

- duplicate task progress or completion events
- duplicate resurfacing/reopen signals
- duplicate meeting action-item tasks
- repeated breakglass or approval state transitions

Mitigation:

- first shim prototype must not register new background jobs
- keep existing Sparkbot producers as the only live emitters
- if shadow-writing is later introduced, mark adapter-generated events with shim-only correlation metadata and compare without exposing them to production readers

## 7. Dashboard/API compatibility risks

The frontend and operator routes are currently coupled to Sparkbot response shapes, not just raw storage rows.

Known compatibility dependencies:

- `SpineTaskResponse` exposes decoded `depends_on`, `tags`, and Sparkbot-only subsystem fields
- `SpineProjectResponse` exposes source and ownership fields not present directly in LIMA core models
- `SpineTMOverview` expects specific queue names and `project_workload_summary` structure
- operator endpoints return wrapper objects with `{tasks, count}`, `{events, count}`, `{projects, count}`, and producer counts
- task detail view expects lineage + approvals + handoffs in one response

Implication:

Sparkbot must keep its route-layer formatters and response models even after storage delegation starts. The shim should feed those formatters, not replace them.

## 8. Migration dry-run plan

The first real migration exercise must be offline only.

### Phase 1: schema introspection fixture

- copy a Sparkbot test Spine DB to a temp path
- record `sqlite_master` plus `_ensure_schema_migrations()` column set
- assert the shim’s mapping table covers every live column

### Phase 2: read-only translation

- read live Sparkbot rows
- translate them into in-memory LIMA models only
- do not write a LIMA DB yet
- compare representative task/project/event samples field-by-field

### Phase 3: shadow store build

- write translated rows into a temp `SQLiteSpineStore`
- compare counts for tasks, events, projects, relations, and producers
- explicitly report unmapped tables: approvals, handoffs, assignments, project_events

### Phase 4: read-model parity checks

- run queue derivation and dashboard snapshot checks against the Sparkbot source and the shadow store
- mark any queues that still require Sparkbot-side logic

### Phase 5: redaction parity checks

- assert no redacted Sparkbot payload becomes less redacted in the translated model
- assert temp artifacts contain no secret-like values

## 9. Rollback plan

The rollback boundary must be trivial because Sparkbot remains source of truth.

Rollback strategy:

- keep all Sparkbot writes on the existing `guardian_spine_*` tables until parity is proven
- keep the shim disabled by default behind a Sparkbot-local wiring flag or import boundary
- if any parity check fails, drop the temp LIMA DB and route all reads back to current Sparkbot `spine.py`
- never mutate the production Sparkbot Spine DB during the first shim prototype

Operational rule:

If the prototype introduces any ambiguity about which store is canonical, revert the prototype and return to Sparkbot-only Spine immediately.

## 10. Smallest safe prototype PR after this

Recommended next PR:
`PR 4E — read-only Sparkbot Spine compatibility probe`

Scope:

- add Sparkbot-side test-only translator helpers that map live Sparkbot rows into LIMA `SpineTask`, `SpineProject`, `SpineEventEnvelope`, and `SpineRelation`
- build a temp `SQLiteSpineStore` from copied test data only
- add parity tests for:
  - task field mapping
  - project field mapping
  - event category derivation
  - redaction preservation
  - queue-read gaps explicitly marked as unsupported

Out of scope:

- no route changes
- no production import rewiring
- no dual-write
- no live DB migration
- no dashboard changes

Why this is the smallest safe step:

It validates the schema translation and identifies missing Sparkbot-only tables before any runtime behavior changes. That is the hard boundary between the current generic LIMA store and any future Sparkbot adapter shim.
