# Personal finance agent

https://github.com/pypi-ahmad/intelligent-personal-finance-agent

Phase 3: local-first finance copilot — ingest, analyze, remember, and stay private.

Data stays on disk in `data/finance.db`. API keys stay in `.env`.

## Features

- Upload CSV, Excel, PDF, or statement images
- Hybrid categories: rules, then local Ollama leftovers, then the selected API model only if still `OTHER`
- Deduped SQLite ledger (`date` + `description` + `amount`)
- Chat via LangGraph: plan → fetch → brief (insights/budgets) → answer
- Insights: top categories, month vs last month, weekly/monthly charts, anomalies
- Monthly budgets vs actual
- Transaction filters (date, category, search) and editable category
- Monthly/weekly report download as Markdown or PDF
- Deep questions (category + travel window + last quarter), follow-ups with chat history
- Accounts, net worth, recurring detection, savings/debt goals, alerts + weekly digest
- Chat memory across restarts; privacy tab to inspect/delete local data
- Local-first toggle: Ollama only, cloud APIs blocked
- Sidebar model picker: Ollama, OpenAI, Agnes AI, Google

CSV and Excel ingest work with no model. PDF, images, leftover-category fill, and chat need one.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- A model only if you want PDF/image extract, LLM categories, or chat:
  - local [Ollama](https://ollama.com/), or
  - `OPENAI_API_KEY` / `AGNES_API_KEY` / `GOOGLE_API_KEY`

## Getting started

1. Copy env file:

   ```bat
   copy .env.example .env
   ```

2. Fill only the keys you use. Ollama needs no key; optional `OLLAMA_HOST` defaults to `http://localhost:11434`.

3. Start the app:

   Double-click `run.cmd`, or:

   ```bat
   uv sync --all-groups
   uv run streamlit run streamlit_app.py
   ```

`run.cmd` installs uv if missing, copies `.env.example` → `.env` when needed, syncs deps, then starts Streamlit.

> [!NOTE]
> OpenAI, Agnes AI, and Google show an error in the sidebar until the matching key is set. CSV/Excel ingest still works.

## Use it

1. Pick a provider and model in the sidebar (skip for CSV/Excel only).
2. Upload one or more statements → **Ingest files**.
3. Check totals at the top (count, spent, income).
4. **Chat** (memory + follow-ups). **Transactions**, **Insights**, **Plan** (budgets/accounts/goals), **Reports**, **Privacy**.

Amounts: expenses/debits are negative, income/credits positive. Default currency is INR.

### Categories

`FOOD` `GROCERIES` `TRANSPORT` `UTILITIES` `RENT` `SHOPPING` `HEALTH` `ENTERTAINMENT` `TRANSFER` `INCOME` `FEES` `OTHER`

Rules live in `src/finance_agent/categorize.py`.

### Models

| Provider | Models | Key |
| --- | --- | --- |
| Ollama | whatever is installed locally | none |
| OpenAI | `gpt-5.6-luna`, `gpt-5.6-terra` (medium effort) | `OPENAI_API_KEY` |
| Agnes AI | `agnes-2.5-flash` | `AGNES_API_KEY` |
| Google | `gemini-3.5-flash-lite`, `gemini-3.7-flash` | `GOOGLE_API_KEY` |

Optional: `OPENAI_BASE_URL` for an OpenAI-compatible gateway.

## How it works

```
upload → parse → rules → local leftovers → API leftovers → SQLite
question → plan filters → search rows → brief (insights/budgets) → answer
```

| Path | Role |
| --- | --- |
| `streamlit_app.py` | UI |
| `src/finance_agent/ingest.py` | Parse files |
| `src/finance_agent/categorize.py` | Rules + hybrid leftovers |
| `src/finance_agent/insights.py` | Trends, compare, anomalies |
| `src/finance_agent/reports.py` | Markdown / PDF |
| `src/finance_agent/db.py` | SQLite + budgets |
| `src/finance_agent/agent.py` | LangGraph Q&A + follow-ups |
| `src/finance_agent/copilot.py` | Travel filter, recurring, alerts, digest |
| `src/finance_agent/llm.py` | Provider wrappers + local-first gate |

`data/` and `.env` are gitignored.

## Tests

```bat
uv run pytest
```

Covers ingest, hybrid leftover fill, insights, budgets, and report export.

> [!WARNING]
> This is a local Phase 3 tool, not a bank connection. Do not commit `.env` or `data/`.
