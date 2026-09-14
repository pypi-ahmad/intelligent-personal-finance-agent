# Technical reference

Phase 8 machinery. How to run it: [how-to-use.md](how-to-use.md).

Repo: https://github.com/pypi-ahmad/intelligent-personal-finance-agent

## What this system is

A single-process Streamlit app plus the `finance-agent` package. It ingests statement files, stores rows in local SQLite, categorizes them (rules, user rules, learned corrections, then hybrid LLM), and answers questions through LangGraph: plan → fetch → brief → reply.

No bank connection. No public HTTP API. No cron. Digests generate when the app opens on or after that week's Monday (`notify.refresh_inbox`).

## Layout

| Path | Role |
| --- | --- |
| `streamlit_app.py` | UI: sidebar + eight tabs |
| `config.py` | Paths, providers, model IDs, `env()` |
| `llm.py` | Ollama list, OpenAI-compat, Google, local-only gate |
| `ingest.py` | File parse → row dicts + merchant |
| `merchants.py` | Alias map (Amazon, Swiggy, Uber Eats, …) |
| `categorize.py` | User rules → corrections → builtins → hybrid LLM + few-shot |
| `db.py` | SQLite, export zip, notifications |
| `agent.py` | LangGraph Q&A |
| `insights.py` | Series, month compare, MAD anomalies, budgets |
| `copilot.py` | Travel, recurring, alerts, digest, net worth, goals |
| `dashboard.py` | Forecast, inflation, cancel suggestions, chart series |
| `notify.py` | Monday inbox refresh |
| `reports.py` | Month / week / tax-year Markdown + PDF |
| `vault.py` | Optional passphrase lock (`PFENC1` + Fernet) |
| `tests/` | `test_phase1.py` … `test_phase6.py`, `test_phase8.py` |

Python `>=3.11`. Tooling: uv, ruff, ty, pytest. Extra runtime: `cryptography`, `fpdf2`.

## Configuration

`load_dotenv(override=False)`. `env(name)` uses a non-empty process value, then Windows `HKCU\Environment`.

| Variable | Used by |
| --- | --- |
| `OPENAI_API_KEY` | OpenAI |
| `OPENAI_BASE_URL` | Optional gateway |
| `AGNES_API_KEY` | Agnes |
| `GOOGLE_API_KEY` | Gemini |
| `OLLAMA_HOST` | Default `http://localhost:11434` |

Agnes base URL is code: `https://apihub.agnes-ai.com/v1`. Model: `agnes-2.5-flash`.

OpenAI: `gpt-5.6-luna`, `gpt-5.6-terra`, `reasoning_effort=medium`.

Google: `gemini-3.5-flash-lite`, `gemini-3.7-flash`.

Ollama: `GET {OLLAMA_HOST}/api/tags`, sorted.

`is_local_only()` (`settings.local_only`) makes `complete()` raise `PermissionError` unless the provider is Ollama.

## Storage

`data/finance.db`. Created on connect. Gitignored.

| Table | Purpose |
| --- | --- |
| `transactions` | Ledger + `merchant`, `parent_id` |
| `budgets` | category × `YYYY-MM` |
| `accounts` | asset / liability balances |
| `goals` | savings / debt |
| `messages` | Chat memory |
| `settings` | `local_only` |
| `user_rules` | Custom description needles |
| `corrections` | Learned merchant → category |
| `notifications` | Inbox, unique `dedupe` |

Dedup key: `date` + `description` + `amount`. `amount < 0` is spend.

`export_zip()` writes `data.json` + `transactions.csv`.

Optional lock: `vault.lock_db(passphrase)` writes `data/finance.db.enc` (`PFENC1` + salt + Fernet) and deletes plaintext. Unlock reverses. Passphrase is not stored.

## Categorize order

1. User rules (`needle` in description)
2. Latest correction for merchant / normalized description
3. Builtin `RULES`
4. Leftover `OTHER` → local Ollama (few-shot from corrections) → selected API unless local-only

`update_category` writes a correction. Split replaces one row with two parts that must sum to the original.

## LangGraph

`ask(question, provider, model, history=None)`:

`START → plan → fetch → brief → reply → END`

- **plan**: JSON filters; `infer_range` fills last quarter / month / week; travel flag
- **fetch**: `search()`; travel days from `TRAVEL_NEEDLES` ±1 day
- **brief**: `snapshot()` + learned merchant=category
- **reply**: last eight chat lines + context only

## Dashboard and inbox

- Charts from `dashboard.py` (Altair in the UI)
- Forecast: last-30-day run-rate + recurring in the horizon
- Lifestyle inflation: last 3 complete months vs prior 3
- Cancel list: recurring × 12 or 52
- `refresh_inbox(today)` inserts digest / week / anomaly / bill / goal rows once per `dedupe` key

## UI

Tabs (`on_change="rerun"`): Dashboard, Notifications, Chat, Transactions, Insights, Plan, Reports, Privacy.

Theme: `.streamlit/config.toml` defines `[theme.light]` and `[theme.dark]` so the Streamlit menu can switch. `gatherUsageStats = false`. `run.cmd` / `run.sh` bind `--server.address localhost`.

If `vault.is_locked()`, the script stops at an unlock form before any other DB read.

## Commands

| Command | Purpose |
| --- | --- |
| `run.cmd` / `bash run.sh` | First-time uv + `.venv` + start on localhost |
| `uv sync --all-groups --python <venv python>` | Install into `.venv` |
| `<venv python> -m streamlit run streamlit_app.py --server.address localhost` | Serve |
| `<venv python> -m pytest` | Tests (35) |
| `<venv python> -m ruff check` | Lint |

`<venv python>` is `.venv\Scripts\python.exe` on Windows and `.venv/bin/python` on Linux.

No Makefile. No CI in the tree.

## Out of scope

Bank aggregators, multi-user auth, hosted deploy, cron, SQLCipher (file-level Fernet lock instead).
