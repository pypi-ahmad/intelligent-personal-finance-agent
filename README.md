# Personal finance agent

https://github.com/pypi-ahmad/intelligent-personal-finance-agent

Local-first Phase 8 copilot: private ledger, dashboard first, optional encryption, tax export.

[How to use](docs/how-to-use.md) · [Technical reference](docs/technical.md)

## Features

- Upload CSV, Excel, PDF, or statement images
- Hybrid categories: rules → local Ollama leftovers → selected API only if still `OTHER`
- SQLite ledger with dedupe (`date` + `description` + `amount`)
- LangGraph chat: plan → fetch → brief → reply, plus follow-ups and saved history
- Insights, budgets vs actual, accounts/net worth, goals, recurring, alerts
- Monthly/weekly report as Markdown or PDF
- Privacy tab (inspect / delete) and a **Local-first** toggle (Ollama only)
- Learns category corrections, normalizes merchants, splits, custom rules
- Dashboard: category spend, income vs expense, savings rate, top merchants, 30/60-day forecast
- Notifications: Monday digest, bills, anomalies, what changed this week
- Privacy: full zip export, optional passphrase lock, tax-year report, dark/light theme

CSV and Excel ingest work with no model. PDF, images, leftover LLM fill, and chat need one.

> [!WARNING]
> Not a bank connection. Do not commit `.env` or `data/`.

## Stack

| Layer | Choice |
| --- | --- |
| Language | Python 3.11+ |
| UI | Streamlit 1.61+ |
| Agent | LangGraph |
| Store | SQLite (`data/finance.db`) |
| Package | uv + `uv.lock` |
| Dev | pytest, ruff, ty |

## Architecture

```
upload → parse → rules → local leftovers → API leftovers → SQLite
question → plan filters → search (+ travel window) → brief → answer
```

Single process. No hosted API. Digests and reports compute when you open the tab.

Details: [docs/technical.md](docs/technical.md)

## Getting started

**Need:** Python 3.11+, [uv](https://docs.astral.sh/uv/). Optional: [Ollama](https://ollama.com/) or cloud keys.

1. Keys come from this machine first: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `AGNES_API_KEY`, `GOOGLE_API_KEY`.
2. On a new machine with no OS vars, copy `.env.example` → `.env` and fill only what you use.
3. Start:

   Double-click `run.cmd`, or:

   ```bat
   uv sync --all-groups
   uv run streamlit run streamlit_app.py
   ```

`run.cmd` installs uv if missing, syncs deps, starts Streamlit. It does **not** create a blank `.env`.

> [!NOTE]
> Sidebar errors on a missing cloud key. CSV/Excel ingest still works.

**Use it:** pick provider/model → ingest files → **Dashboard**, **Notifications**, **Chat**, **Transactions**, **Insights**, **Plan**, **Reports**, **Privacy**. Dark/light is in the Streamlit menu.

Expenses are negative, income positive. Default currency is INR.

Full walkthrough: [docs/how-to-use.md](docs/how-to-use.md)

## Models

| Provider | Models | Key |
| --- | --- | --- |
| Ollama | all local models from `/api/tags` | none (`OLLAMA_HOST` optional) |
| OpenAI | `gpt-5.6-luna`, `gpt-5.6-terra` (medium effort) | `OPENAI_API_KEY`, optional `OPENAI_BASE_URL` |
| Agnes AI | `agnes-2.5-flash` | `AGNES_API_KEY` |
| Google | `gemini-3.5-flash-lite`, `gemini-3.7-flash` | `GOOGLE_API_KEY` |

Agnes base URL is fixed: `https://apihub.agnes-ai.com/v1`.

## Project structure

```
streamlit_app.py          UI
src/finance_agent/        package
  ingest.py               parse files
  categorize.py           rules + hybrid leftovers
  db.py                   SQLite
  agent.py                LangGraph
  insights.py / copilot.py
  llm.py / reports.py
docs/                     how-to + technical
tests/                    phase 1–3
```

## Testing

```bat
uv run pytest
uv run ruff check
```

Covers parse/rules, hybrid leftovers, insights/budgets/reports, travel/recurring/memory/local-first.
