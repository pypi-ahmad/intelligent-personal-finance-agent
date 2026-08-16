# Technical reference

Information-oriented description of the Phase 3 codebase. For operating the UI see [how-to-use.md](how-to-use.md).

Repo: https://github.com/pypi-ahmad/intelligent-personal-finance-agent

## What this system is

A single-process Streamlit app plus the `finance-agent` package. It ingests statement files, stores rows in local SQLite, categorizes them, and answers questions through a LangGraph plan → fetch → brief → reply loop.

It does not connect to a bank. There is no HTTP API and no background scheduler. "Automatic" reports and digests are computed when you open the tab.

## Layout

| Path | Role |
| --- | --- |
| `streamlit_app.py` | Entire UI: sidebar + six tabs |
| `src/finance_agent/config.py` | Paths, providers, model IDs, `env()` |
| `src/finance_agent/llm.py` | Ollama list, OpenAI-compat, Google GenAI, local-first gate |
| `src/finance_agent/ingest.py` | File parse → normalized row dicts |
| `src/finance_agent/categorize.py` | Rules, leftover LLM, hybrid local-then-API |
| `src/finance_agent/db.py` | SQLite schema and queries |
| `src/finance_agent/agent.py` | LangGraph Q&A |
| `src/finance_agent/insights.py` | Spend series, month compare, MAD anomalies |
| `src/finance_agent/copilot.py` | Travel window, recurring, alerts, digest, net worth |
| `src/finance_agent/reports.py` | Monthly/weekly Markdown and PDF |
| `tests/` | `test_phase1.py`, `test_phase2.py`, `test_phase3.py` |
| `run.cmd` | Windows bootstrap + `uv run streamlit` |
| `.env.example` | Template only; not required if OS env is set |

Python floor: `requires-python = ">=3.11"`. Tooling: `uv`, `ruff`, `ty`, `pytest`.

## Configuration and secrets

`load_dotenv(override=False)` so process/user environment wins. `env(name)` returns a non-empty process value, then (on Windows) `HKCU\Environment` if the process value is empty.

| Variable | Used by |
| --- | --- |
| `OPENAI_API_KEY` | OpenAI chat |
| `OPENAI_BASE_URL` | Optional OpenAI-compatible gateway |
| `AGNES_API_KEY` | Agnes chat |
| `GOOGLE_API_KEY` | Gemini |
| `OLLAMA_HOST` | Default `http://localhost:11434` |

Agnes base URL is code, not env: `https://apihub.agnes-ai.com/v1`. Model id: `agnes-2.5-flash`.

OpenAI model: `gpt-5.6-luna` with `reasoning_effort=medium` (retried without that kwarg if the API rejects it).

Google models: `gemini-3.5-flash-lite`, `gemini-3.7-flash`.

Ollama models: live `GET {OLLAMA_HOST}/api/tags`, sorted.

`is_local_only()` is a SQLite setting (`settings.local_only`). When on, `complete()` raises `PermissionError` for any provider other than Ollama.

## Storage

File: `data/finance.db` (`DATA_DIR` / `DB_PATH`). Directory is created on connect. Gitignored.

| Table | Purpose |
| --- | --- |
| `transactions` | Ledger. Dedup on `date` + `description` + `amount` |
| `budgets` | `(category, period YYYY-MM)` → amount |
| `accounts` | `name`, `kind` (`asset`/`liability`), `balance` |
| `goals` | savings/debt target, current, deadline |
| `messages` | Chat memory (`role`, `content`, `created_at`) |
| `settings` | Key/value, including `local_only` |

`amount < 0` is spend; `amount > 0` is income. Default currency `INR`.

`search()` filters: `start_date`, `end_date`, `category`, `text`, `account`. Limit clamped 1–500.

Wipe helpers: `clear_messages`, `wipe_ledger`, `wipe_all` (does not drop `settings`).

## Ingest

`parse_file(name, data, llm_extract=None)`:

| Suffix | Path |
| --- | --- |
| `.csv` / `.tsv` | pandas → column-name heuristics |
| `.xlsx` / `.xls` | pandas Excel → same table mapper |
| `.pdf` | pypdf text → LLM JSON if callback, else loose regex lines |
| `.png` `.jpg` `.jpeg` `.webp` | LLM + image bytes; no callback → error |

Debit columns become negative; credit columns positive. Every row then gets `apply_rules(description)`.

Hybrid leftover fill (`categorize_hybrid`):

1. Rows already rule-tagged.
2. Remaining `OTHER` → first available Ollama model (or the selected Ollama model).
3. Still `OTHER` → selected cloud model, unless local-first is on.

## LangGraph

`ask(question, provider, model, history=None)` compiles a cached graph:

`START → plan → fetch → brief → reply → END`

- **plan** — LLM returns JSON filters. If dates are missing, `infer_range` fills "last quarter" / "this month" / "last month" / "last week". `travel` is true if the model says so or the question matches travel words.
- **fetch** — `search()`. If `travel`, keep rows on travel dates (±1 day around `TRAVEL_NEEDLES` in descriptions), then apply category.
- **brief** — `insights.snapshot()` text (month compare, top cats, anomaly count, budgets).
- **reply** — LLM answer from transactions + brief + last eight history lines.

The model is not allowed to invent amounts; the prompt says to use only provided context.

## Insights and copilot

- Top categories: abs(spend) by category.
- Month compare: this `YYYY-MM` vs previous month.
- Anomalies: MAD fence; need at least four expenses.
- Recurring: three or more similar descriptions and rounded amounts with weekly or monthly gaps.
- Alerts: over budget, anomaly count, recurring due in seven days, goal behind (< 50% with deadline in 30 days).
- Net worth: sum(asset balances) − sum(liability balances). Manual balances, not derived from the ledger.

## UI map

`streamlit_app.py` tabs (`on_change="rerun"` so hidden tabs do not run):

| Tab | Code path |
| --- | --- |
| Chat | `ask` + `append_message` / `list_messages` |
| Transactions | `search` + `update_category` / `update_account` |
| Insights | insights + `alerts` + `detect_recurring` + `weekly_digest` |
| Plan | `upsert_budget` / `upsert_account` / `upsert_goal` |
| Reports | `month_markdown` / `week_markdown` / `report_pdf` |
| Privacy | `privacy_stats`, deletes |

Sidebar owns Local-first, provider, model (`key=f"model_{provider}"`), upload, hybrid checkbox, ingest account.

## Commands

| Command | Purpose |
| --- | --- |
| `uv sync --all-groups` | Install runtime + dev tools |
| `uv run streamlit run streamlit_app.py` | Serve UI |
| `uv run pytest` | All tests |
| `uv run ruff check` | Lint |

No Makefile. No CI workflow in the tree.

## Out of scope

Bank aggregators, multi-user auth, hosted deploy, cron, DuckDB, and any model IDs other than those listed above.
