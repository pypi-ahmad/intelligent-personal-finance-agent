# How to use the personal finance agent

Recipe for running the Phase 8 app. Internals: [technical.md](technical.md).

Need a network connection the first time. Native Windows or native Linux (no Docker, no WSL). A model is optional for CSV/Excel only.

## Start

1. Open the project folder.
2. **Windows:** double-click `run.cmd`. **Linux:** `bash run.sh`. Leave the terminal open.

First launch (if tools or `.venv` are missing):

1. Installs [uv](https://docs.astral.sh/uv/) if it is not on PATH.
2. Installs Python 3.11+ via `uv python install`.
3. Creates `.venv` with `uv venv`.
4. Runs `uv sync --all-groups` **into that venv**.
5. Copies `.env.example` → `.env` only when `.env` does not exist. Empty lines do not overwrite OS env vars.
6. Starts Streamlit with the venv Python on `localhost`.

Later launches reuse `.venv`, sync, and start.

```bash
# Linux
uv python install
uv venv .venv
uv sync --all-groups --python .venv/bin/python
.venv/bin/python -m streamlit run streamlit_app.py --server.address localhost

# Windows (same steps; python is .venv\Scripts\python.exe)
```

Leave the terminal open. Dark/light: Streamlit menu (⋮).

If you see **Unlock database**, the ledger was locked. Enter the passphrase you set on **Privacy**.

## Keys (cloud models only)

The app reads **this machine's environment first**. Empty `.env` lines do not overwrite user env vars.

| You want | Set on the machine |
| --- | --- |
| OpenAI `gpt-5.6-luna` or `gpt-5.6-terra` (medium) | `OPENAI_API_KEY`, optional `OPENAI_BASE_URL` |
| Agnes `agnes-2.5-flash` | `AGNES_API_KEY` |
| Gemini `gemini-3.5-flash-lite` or `gemini-3.7-flash` | `GOOGLE_API_KEY` |
| Local Ollama | none (optional `OLLAMA_HOST`) |

On a new machine with no OS vars, copy `.env.example` → `.env`. Do not commit `.env`.

Ollama: start Ollama, pull a model. The sidebar lists `/api/tags`.

## Local-only

Sidebar **Local-only** on = Ollama only. OpenAI, Agnes, and Google are blocked in code.

## Ingest

1. Pick provider and model (skip for CSV/Excel).
2. Optional: assign to an account from **Plan**.
3. Upload PDF, CSV, Excel, or images → **Ingest files**.
4. Leave **Hybrid leftover categories** on unless you want rules only.

Duplicates (`date` + `description` + `amount`) are skipped. Expenses are negative. Default currency is INR.

## Tabs

| Tab | Use it for |
| --- | --- |
| **Dashboard** | Landing: charts, 30/60-day cashflow, inflation, budgets, cancel-these |
| **Notifications** | Monday digest, bills, unusual spend, week change, goals |
| **Chat** | Questions and follow-ups (history saved) |
| **Transactions** | Filter, edit category (learns), edit account, split |
| **Insights** | Trends, recurring, alerts, weekly digest download |
| **Plan** | Budgets, custom rules, accounts, goals |
| **Reports** | Month, week, or **Tax year** → Markdown / PDF |
| **Privacy** | What is stored, zip export, lock DB, delete data |

## Learn from corrections

Change **Category** on **Transactions**. The app stores that merchant → category and reuses it on the next ingest. Few-shot examples also go to leftover LLM fill.

**Plan → Custom category rules:** if description contains X, use category Y. Those beat builtins.

## Split a row

On **Transactions**, use **Split a transaction**. Two parts must sum to the original amount.

## Export and lock

- **Privacy → Download full export (zip):** `data.json` + `transactions.csv`
- **Privacy → Lock database:** passphrase encrypts `data/finance.db`. The next launch asks to unlock. Remember the passphrase; it is not stored.
- Wipe: delete chat, delete transactions, or type `DELETE` to wipe almost everything

## If something fails

| Symptom | What to do |
| --- | --- |
| Missing `*_API_KEY` | Set the user env var, close the terminal, run `run.cmd` or `bash run.sh` again |
| Ollama: no models | Start Ollama, `ollama pull <name>`, refresh |
| Local-only hides cloud providers | Expected |
| Unlock screen | Enter the lock passphrase |
| PDF/image ingest fails | Select a model first |
| Re-upload adds 0 rows | Same date/description/amount already stored |
