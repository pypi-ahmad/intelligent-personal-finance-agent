# Contributing

Thank you for considering a contribution. This project is **free**, **MIT-licensed**, and **community-driven**. Issues, discussions, documentation fixes, tests, and pull requests are welcome.

The author does **not** accept donations, sponsorships, or paid feature requests. Please do not include funding offers in issues or PRs.

You run the app on **your** machine with **your** keys. Never commit `.env`, `data/`, `*.db.enc`, or real statements.

## Ways to help

- Use the app and [report bugs](.github/ISSUE_TEMPLATE/bug_report.md)
- [Suggest features](.github/ISSUE_TEMPLATE/feature_request.md) that fit a **local-first** personal ledger
- Improve docs (`README.md`, `docs/how-to-use.md`, `docs/technical.md`)
- Add or tighten tests under `tests/`
- Fix small, well-scoped bugs

If you are unsure, open an issue before a large PR so we can agree on scope.

## Before you start

**Need:** [uv](https://docs.astral.sh/uv/) (the launchers install it). Native Windows or native Linux.

```bash
git clone https://github.com/pypi-ahmad/intelligent-personal-finance-agent.git
cd intelligent-personal-finance-agent
# Windows: run.cmd    Linux: bash run.sh
# or by hand:
uv python install
uv venv .venv
uv sync --all-groups --python .venv/bin/python   # Windows: .venv\Scripts\python.exe
.venv/bin/python -m pytest
.venv/bin/python -m ruff check
```

Optional: copy `.env.example` → `.env` for **your** cloud keys. Tests do not need live API keys.

`run.cmd` (Windows) and `run.sh` (Linux) install uv if needed, create `.venv` with `uv venv`, sync into that venv, copy `.env.example` → `.env` only when `.env` is absent, then start Streamlit with the venv Python.

## Architecture rules

Keep the current shape: one Streamlit process + `src/finance_agent/` + SQLite.

1. **Domain logic** goes in `src/finance_agent/`, not in `streamlit_app.py` (widgets and wiring only).
2. **Persist** through `db.py` (`SCHEMA` + `_migrate` if existing user DBs must survive).
3. **LLM calls** go through `llm.complete` so **Local-only** cannot be bypassed.
4. **Do not** add a hosted API, bank connector, donation link, telemetry, or secret collection.
5. **Do not** store the vault passphrase.
6. Prefer functions and dict rows. Do not introduce a DI container or extra process unless an issue agrees.

Details: [ARCHITECTURE.md](ARCHITECTURE.md), [docs/technical.md](docs/technical.md), [Project_Architecture_Blueprint.md](Project_Architecture_Blueprint.md).

## Tests and lint

```bash
.venv/bin/python -m pytest          # Linux
.venv\Scripts\python.exe -m pytest  # Windows
.venv/bin/python -m ruff check
```

- Add a focused test next to the phase files (`tests/test_phase1.py` … `test_phase6.py`, `test_phase8.py`) or a small new `tests/test_*.py`.
- Use `tmp_path` + `monkeypatch` for `DB_PATH` / `DATA_DIR` when touching SQLite.
- Inject fake `complete` callables; do not call live OpenAI / Agnes / Google / Ollama in CI-style tests.
- There is no Streamlit e2e suite. Do not require a long-running frontend to prove a unit of logic.

## Pull requests

1. Fork (or branch from `main`).
2. Keep the diff small and one concern per PR.
3. Use the [pull request template](.github/PULL_REQUEST_TEMPLATE.md).
4. Confirm pytest and ruff pass using the project `.venv` Python.
5. Describe what you ran. Do not paste statement contents, keys, or passphrases.

PRs that add sponsorship buttons, analytics, or “phone home” will be declined.

## Code style

- Match the file you are in: short functions, explicit names, no speculative layers.
- Ruff is configured in `pyproject.toml` (`select = ALL` with listed ignores).
- `ty` targets Python 3.11.

## Conduct

Be respectful. Assume good faith. This is a small personal-finance tool people run on private data — treat that seriously.

Questions about **using** the app belong in [SUPPORT.md](SUPPORT.md), not in a PR.
