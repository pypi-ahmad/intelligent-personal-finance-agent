## What

Briefly describe the change.

## Why

Link the issue if there is one (`Fixes #123`).

## How you tested

- [ ] `uv run pytest`
- [ ] `uv run ruff check`
- [ ] Manual check (say which tab / command). Do **not** paste real ledger data.

## Checklist

- [ ] Logic lives in `src/finance_agent/` unless this is a widget-only UI change
- [ ] SQLite changes include `SCHEMA` and `_migrate` when existing DBs must keep working
- [ ] LLM traffic still goes through `llm.complete` (Local-only still holds)
- [ ] No secrets, `.env`, `data/`, or statement files in the diff
- [ ] No donation, telemetry, or remote-account features

## Notes for reviewers

Anything risky (vault, categorize order, dedupe, wipe)?
