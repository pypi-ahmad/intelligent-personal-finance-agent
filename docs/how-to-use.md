# How to use the personal finance agent

This is a recipe for running the local app and doing the usual jobs. It is not an architecture write-up. For internals see [technical.md](technical.md).

You need Windows, Python 3.11+, and [uv](https://docs.astral.sh/uv/). A model is optional for CSV/Excel ingest only.

## Start the app

1. Open the project folder.
2. Double-click `run.cmd`.

`run.cmd` installs `uv` if needed, runs `uv sync --all-groups`, then starts Streamlit.

Same thing in a terminal:

```bat
uv sync --all-groups
uv run streamlit run streamlit_app.py
```

The UI opens in the browser. Leave the terminal window open while you work.

## Give it keys (only if you use a cloud model)

The app reads **this machine's environment first**. It does not overwrite a user/process variable with an empty `.env` line.

| You want | Set on the machine |
| --- | --- |
| OpenAI `gpt-5.6-luna` (medium effort) | `OPENAI_API_KEY`, optional `OPENAI_BASE_URL` |
| Agnes `agnes-2.5-flash` | `AGNES_API_KEY` |
| Gemini `gemini-3.5-flash-lite` or `gemini-3.7-flash` | `GOOGLE_API_KEY` |
| Local Ollama | none (optional `OLLAMA_HOST`, default `http://localhost:11434`) |

On a new machine that has no OS env vars, copy `.env.example` to `.env` and fill only the keys you use. Do not commit `.env`.

Ollama: start Ollama and pull at least one model. The sidebar lists whatever `/api/tags` returns.

## Ingest statements

1. Sidebar → pick **Provider** and **Model** (skip for CSV/Excel only).
2. Optional: turn **Local-first** on to block OpenAI, Agnes, and Google.
3. Optional: pick **Assign to account** if you already created an account on **Plan**.
4. Upload PDF, CSV, Excel, or images.
5. Leave **Hybrid leftover categories** on unless you want rules only.
6. Click **Ingest files**.

CSV/Excel parse without a model. PDF, images, leftover LLM categories, and chat need a selected model (and a key unless the provider is Ollama).

Duplicates (`date` + `description` + `amount`) are skipped. Expenses are negative; income is positive. Default currency is INR.

## Ask questions

Open **Chat**.

- First visit: use a suggestion pill, or type a question.
- Follow-ups work. The last eight turns are sent with the new question.
- Chat is stored in `data/finance.db` and comes back after restart.

Useful shapes:

- "What did I spend last month?"
- "How much did I spend on FOOD?"
- "How much did I spend on food while traveling last quarter?"
- "Any unusual transactions this month?"

If the sidebar says a key is missing, chat will refuse until you set it (or switch to Ollama).

## Browse and fix the ledger

Open **Transactions**.

1. Set date range, category, account, and description search.
2. Change **Category** or **Account** in the table. Those two columns save; the rest do not.

## Read insights

Open **Insights**.

You get this month vs last month, top categories, monthly/weekly charts, alerts, recurring payments (needs three similar expenses), unusual amounts, and a **Download weekly digest** button.

## Set budgets, accounts, and goals

Open **Plan**.

- **Month** as `YYYY-MM`, then save a category budget. Progress is actual spend vs that limit.
- **Accounts**: name, kind (`asset` or `liability`), balance. Net worth is assets minus liabilities (the number you typed, not a live bank feed).
- **Goals**: savings or debt, target, current/paid, deadline.

## Export a report

Open **Reports**.

1. Choose **Month** or **Week**.
2. Preview the Markdown.
3. Download `.md` or `.pdf`.

## Check privacy or delete data

Open **Privacy**.

You see the SQLite path and row counts. You can:

- delete chat history
- delete transactions only
- type `DELETE` and wipe ledger, chat, budgets, accounts, and goals

`data/` is gitignored. This is not a bank connection.

## If something fails

| Symptom | What to do |
| --- | --- |
| Sidebar: missing `OPENAI_API_KEY` / `AGNES_API_KEY` / `GOOGLE_API_KEY` | Set the user env var, close the terminal, run `run.cmd` again |
| Ollama: no models | Start Ollama, `ollama pull <name>`, refresh |
| Local-first on, cloud provider gone | Expected. Turn the toggle off to use OpenAI/Agnes/Google |
| PDF/image ingest fails | Select a model first |
| Re-upload adds 0 rows | Same date/description/amount already stored |
| Chat forgets after restart | Check **Privacy** message count; do not delete `data/finance.db` |
