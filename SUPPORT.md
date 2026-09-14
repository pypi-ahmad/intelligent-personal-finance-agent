# Support

This is a free, community-driven project. There is no paid support line, no SLA, and no donations or sponsorship. Please do not ask how to send money: it is not wanted.

You run the software on your own computer with your own API keys. Nobody else can see your ledger unless you send it somewhere (for example a cloud model you enable).

## Help yourself first

1. [docs/how-to-use.md](docs/how-to-use.md): start, keys, tabs, lock/unlock
2. [docs/technical.md](docs/technical.md): env vars, tables, categorize order
3. [DISCLAIMER.md](DISCLAIMER.md): data and legal responsibility
4. Common symptoms:

| Symptom | What to try |
| --- | --- |
| Missing `*_API_KEY` | Set the user environment variable, close the terminal, run `run.cmd` or `bash run.sh` again |
| Ollama: no models | Start Ollama, `ollama pull <name>`, refresh the sidebar |
| Local-only hides cloud providers | Expected. Turn Local-only off to see OpenAI / Agnes / Google |
| Unlock screen | Enter the passphrase you set on **Privacy**. It is not stored anywhere |
| PDF/image ingest fails | Select a model first |
| Re-upload adds 0 rows | Same `date` + `description` + `amount` already stored |
| Chat or leftover fill blocked | Local-only is on, or the selected cloud key is missing |

CSV and Excel ingest work with no model.

## Ask the community

- Usage questions and "how do I...": open a GitHub issue and say it is a question. Redact all real amounts, account numbers, and keys.
- Bugs: [bug report template](.github/ISSUE_TEMPLATE/bug_report.md)
- Ideas: [feature request template](.github/ISSUE_TEMPLATE/feature_request.md)
- Code: [CONTRIBUTING.md](CONTRIBUTING.md)

Please be patient and kind. Responses come from volunteers (including you).

## What we cannot do

- Recover a forgotten vault passphrase
- Provide financial, tax, or investment advice
- Process your statements for you
- Accept funds, gifts, or "just buy a coffee"
- Debug a machine we cannot see if the report has no repro steps

## Security issues

Do not post those in public issues. See [SECURITY.md](SECURITY.md).
