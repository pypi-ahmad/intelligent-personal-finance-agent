# Disclaimer

This software is a local personal-finance helper you clone and run yourself. It is provided under the [MIT License](LICENSE) **as is**, without warranty of any kind.

## Your machine, your keys, your data

- The maintainers do not host this app for you and do not receive your files or credentials.
- Any API keys (`OPENAI_API_KEY`, `AGNES_API_KEY`, `GOOGLE_API_KEY`, and related settings) are yours. You create them, you pay the provider if they charge you, and you keep them off GitHub.
- All data processed by the app is your responsibility, including bank and card statements, PDFs, images, merchant names, chat prompts and answers, budgets, goals, exports, and the SQLite database (`data/finance.db` or `data/finance.db.enc`).
- If you turn off **Local-only** and select OpenAI, Agnes, or Google, you send prompt content (and possibly images) to that provider under its terms. The author does not control those services.
- If you lock the database, the passphrase is not stored. Lose it and the encrypted file cannot be opened. That is by design.

You must decide what is safe to ingest, whether to use a cloud model, how to back up `data/`, and whether this tool is appropriate for your situation.

## Not professional advice

This project is not:

- A bank, broker, payment processor, or tax-filing service
- A substitute for a qualified accountant, tax adviser, or financial adviser
- A guarantee of correct categorization, forecasts, tax-year summaries, or "unusual spend" flags
- An official connection to any bank or UPI app

Reports (month, week, tax year) are generated from your stored rows. Verify numbers before you rely on them.

## No financial support

The project is free and community-driven. The author does not want donations, sponsorship, patronage, or paid support. Do not send money.

## Liability

To the maximum extent permitted by law, the authors and contributors are **not liable** for lost data, leaked statements, model bills, tax mistakes, or any other loss arising from use of this software. See the warranty disclaimer in [LICENSE](LICENSE).

If you cannot accept these terms, do not use the software.
