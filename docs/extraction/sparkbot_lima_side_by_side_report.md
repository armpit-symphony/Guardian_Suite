# Sparkbot LIMA Side-by-Side Report

Date: 2026-05-02
Status: Reporting only
Target branch: `pr4k-sparkbot-lima-side-by-side-report`

## Purpose

This report aggregates the existing copied-data-only comparison layers into one Sparkbot-vs-LIMA view.

It is meant to summarize:

- Sparkbot schema readiness
- LIMA translation coverage
- read-only queue and route-shape coverage
- field-level compatibility
- serializer fixture compatibility
- redaction behavior
- known gaps still blocking runtime wiring

## How to run

```bash
python3 tools/spine_side_by_side_report.py \
  --source-db /path/to/copied-or-test-spine.db \
  --output-dir /tmp/spine-side-by-side-report
```

## Safety model

- the source DB path is treated as read-only
- the tool copies the DB to a temp location first
- all comparison layers run against copied/temp data only
- no Sparkbot runtime imports are used
- no FastAPI, dashboard, or route wiring changes occur
- no live DB writes occur

## Expected outputs

- `side_by_side_summary.json`
- `side_by_side_report.md`

## How to interpret pass/fail/gaps

- pass/fail shows which comparison layers currently hold
- Sparkbot side summarizes schema and source coverage
- LIMA side summarizes the extracted comparison stack
- known gaps highlight missing schema coverage, unsupported tables, or parity areas that still need work

## What this report does not do

- it does not migrate data
- it does not rewire Sparkbot runtime
- it does not enable dual-write
- it does not validate HTTP transport or auth behavior

## Roadmap inputs produced by the report

The report is intended to guide the next guarded extraction steps by showing:

- which schema areas are ready for broader parity checks
- which Sparkbot-only tables are still outside LIMA core coverage
- which read-only route surfaces are safe to extend next
