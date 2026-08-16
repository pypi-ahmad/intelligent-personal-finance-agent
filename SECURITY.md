# Security

Thank you for helping keep people who run this app safer. The ledger, chat history, and optional cloud prompts can contain sensitive financial information.

## How this app is meant to run

- **Local only.** There is no official hosted instance. You clone the repo and run Streamlit on `localhost`.
- **Your credentials.** `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `AGNES_API_KEY`, `GOOGLE_API_KEY`, and `OLLAMA_HOST` come from **your** environment (or a local `.env` that must never be committed). Maintainers do not collect keys.
- **Your data.** SQLite lives at `data/finance.db` (gitignored). An optional lock writes `data/finance.db.enc` (`PFENC1` + salt + Fernet) and deletes the plaintext. The passphrase is **not** stored. Forgetting it means the file cannot be recovered by the author.
- **Local-only toggle** blocks cloud `complete()` calls so leftovers and chat stay on Ollama.

You are responsible for the files you ingest, the models you call, and backups of `data/`.

## What to report

Please report in private if you find:

- A way to read or overwrite `finance.db` without going through the app’s intended UI (when used as documented)
- A bypass of **Local-only** that still calls OpenAI, Agnes, or Google
- Path traversal or secret leakage in export/zip, ingest, or reports
- Vault issues (`lock_db` / `unlock_db`) that expose plaintext or weaken `PFENC1`
- Anything that would send user data to a host this repo does not already document

## What not to report as a vulnerability

- “I uploaded my bank CSV and the app stored it” — that is the product
- Missing bank-grade multi-user auth — this is a single-machine tool with no accounts
- Cloud providers logging prompts — that is the provider you chose and the keys you set
- Lost vault passphrase — there is no back door

## How to report

**Do not** open a public issue with exploit details, keys, or sample statements.

1. Use GitHub **Security advisories** on this repository:  
   https://github.com/pypi-ahmad/intelligent-personal-finance-agent/security/advisories/new  
   or email the author via the address on their GitHub profile if advisories are unavailable.
2. Include a minimal repro that uses **synthetic** amounts and fake merchants.
3. Allow reasonable time for a fix before public disclosure.

## Supported versions

There are no numbered security-support windows. `main` is the current line. If you run a fork or an old clone, merge or rebase before assuming a fix applies.

## Please do not

- Offer a bug bounty (none exists; money is not wanted)
- Commit `.env` or database files in a “repro” PR
- Ask the maintainer to decrypt your vault or recover your keys
