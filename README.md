# Personal finance agent

Repository: [github.com/pypi-ahmad/intelligent-personal-finance-agent](https://github.com/pypi-ahmad/intelligent-personal-finance-agent)

A free, local-first Phase 8 copilot: ingest statements, learn your category fixes, and keep the ledger on your own machine. Clone it, run it, test it, file issues, suggest features, and send pull requests.

This project is community-driven. There is no hosted product, no account, and no backend that sees your statements. Everything runs on the computer you control, with your own API keys if you choose to use a cloud model.

[How to use](docs/how-to-use.md) · [Technical reference](docs/technical.md) · [Architecture](ARCHITECTURE.md) · [Contributing](CONTRIBUTING.md) · [Support](SUPPORT.md) · [Disclaimer](DISCLAIMER.md) · [Security](SECURITY.md) · [License](LICENSE)

## Contents

- [Free software: no money asked](#free-software-no-money-asked)
- [You run it, you own the risk](#you-run-it-you-own-the-risk)
- [Features](#features)
- [Stack](#stack)
- [Architecture](#architecture)
- [Getting started](#getting-started)
- [Models](#models)
- [Project structure](#project-structure)
- [Testing](#testing)
- [Community](#community)
- [License](#license)

## Free software: no money asked

This software is MIT-licensed and free to use. The author does not want financial help, donations, sponsorships, "buy me a coffee," paid support, or bounty programs. Please do not send money or open issues offering funds. Time, bug reports, and careful pull requests are the only contributions that help.

## You run it, you own the risk

- Run the app only on your own machine.
- Bring your own credentials (`OPENAI_API_KEY`, `AGNES_API_KEY`, `GOOGLE_API_KEY`, optional `OLLAMA_HOST`). The maintainers never receive them and never need them.
- All data you upload, store, encrypt, export, or send to a model is your responsibility. Bank CSVs, PDFs, images, chat history, and the SQLite file stay on your disk, and may leave it if you pick a cloud provider. Read [DISCLAIMER.md](DISCLAIMER.md).

This is not a bank connection, not financial advice, and not a tax professional.

> [!WARNING]
> Do not commit `.env` or `data/`. Do not paste API keys, passphrases, or statement contents into GitHub issues.

## Features

- Upload CSV, Excel, PDF, or statement images
- Hybrid categories: your rules → learned merchants → builtins → local LLM few-shot → API leftovers
- SQLite ledger with dedupe (`date` + `description` + `amount`)
- LangGraph chat with follow-ups and saved history
- Dashboard: spend by category, income vs expense, savings rate, top merchants, 30/60-day forecast
- Budgets, accounts/net worth, goals, splits, recurring, inflation watch
- Notifications: Monday digest, bills, unusual spend, what changed this week
- Reports: month, week, freelancer tax year (Markdown / PDF)
- Privacy: zip export, passphrase lock, one-click delete, **Local-only** toggle

CSV and Excel ingest work with no model. PDF, images, leftover LLM fill, and chat need one.

## Stack

| Layer | Choice |
| --- | --- |
| Language | Python 3.11+ |
| UI | Streamlit 1.61+ (dark/light in the app menu) |
| Agent | LangGraph |
| Store | SQLite (`data/finance.db`), optional Fernet lock |
| Package | uv + `uv.lock` |
| Dev | pytest, ruff, ty |
| License | [MIT](LICENSE) |

## Architecture

```
upload → parse → merchant → learned/rules → hybrid LLM → SQLite
question → plan filters → search (+ travel) → brief → answer
open app → refresh_inbox (Monday digest if due)
```

Single process. No hosted API. Digests run when you open the app, not as a Windows service.

Details: [docs/technical.md](docs/technical.md) · [ARCHITECTURE.md](ARCHITECTURE.md)

## Getting started

**Need:** a network the first time. Native Windows (`run.cmd`) or native Linux (`run.sh`). No Docker or WSL required. Optional later: [Ollama](https://ollama.com/) or cloud keys you create.

```bash
git clone https://github.com/pypi-ahmad/intelligent-personal-finance-agent.git
cd intelligent-personal-finance-agent
```

| OS | Start |
| --- | --- |
| Windows (native) | Double-click `run.cmd` |
| Linux | `bash run.sh` |

First launch installs [uv](https://docs.astral.sh/uv/) if needed, makes a project `.venv` with `uv venv`, syncs deps **into that venv**, copies `.env.example` → `.env` only when `.env` is absent, then starts Streamlit with the venv Python (`localhost`).

Or by hand (venv Python path is `.venv\Scripts\python.exe` on Windows, `.venv/bin/python` on Linux):

```bash
uv python install
uv venv .venv
uv sync --all-groups --python .venv/bin/python
.venv/bin/python -m streamlit run streamlit_app.py --server.address localhost
```

Keys come from this machine first: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `AGNES_API_KEY`, `GOOGLE_API_KEY`. Fill `.env` only if those are unset. Empty `.env` lines do not overwrite user env vars.

> [!NOTE]
> Sidebar errors on a missing cloud key. CSV/Excel ingest still works. Locked DBs show an unlock screen first.

**Use it:** provider/model → ingest → Dashboard (landing), Notifications, Chat, Transactions, Insights, Plan, Reports, Privacy.

Expenses are negative, income positive. Default currency is INR.

Step-by-step usage: [docs/how-to-use.md](docs/how-to-use.md).

## Models

| Provider | Models | Key (yours, on your machine) |
| --- | --- | --- |
| Ollama | all local models from `/api/tags` | none (`OLLAMA_HOST` optional) |
| OpenAI | `gpt-5.6-luna`, `gpt-5.6-terra` (medium effort) | `OPENAI_API_KEY`, optional `OPENAI_BASE_URL` |
| Agnes AI | `agnes-2.5-flash` | `AGNES_API_KEY` |
| Google | `gemini-3.5-flash-lite`, `gemini-3.7-flash` | `GOOGLE_API_KEY` |

Agnes base URL is fixed in code: `https://apihub.agnes-ai.com/v1`.

**Local-only** in the sidebar forces Ollama. OpenAI, Agnes, and Google are blocked in `complete()`.

## Project structure

```
run.cmd / run.sh           Windows / Linux launchers
streamlit_app.py           UI
src/finance_agent/         package
  ingest.py / merchants.py / categorize.py
  db.py / vault.py
  agent.py / llm.py
  insights.py / copilot.py / dashboard.py / notify.py
  reports.py
docs/                      how-to + technical
tests/                     phase 1-6 and 8
```

## Testing

```bash
# Linux
.venv/bin/python -m pytest
.venv/bin/python -m ruff check

# Windows
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check
```

35 tests: parse/rules, hybrid fill, insights, travel/recurring, learning/splits, dashboard, inbox, vault/tax/export.

## Community

| You want to… | Do this |
| --- | --- |
| Report a bug | [Bug report](https://github.com/pypi-ahmad/intelligent-personal-finance-agent/issues/new?template=bug_report.md) |
| Suggest a feature | [Feature request](https://github.com/pypi-ahmad/intelligent-personal-finance-agent/issues/new?template=feature_request.md) |
| Contribute code or docs | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Ask a usage question | [SUPPORT.md](SUPPORT.md) |
| Report a vulnerability | [SECURITY.md](SECURITY.md) |

Please be kind. Newcomers and first-time contributors are welcome. Keep issues free of personal financial data.

## License

[MIT](LICENSE) © 2026 Ahmad Mujtaba. Use, copy, modify, and share freely. The software is provided **as is**, without warranty.

<p align="center">Made with ❤️ by Ahmad Mujtaba</p>
