# Graph Report - Intelligent Personal Finance Agent  (2026-08-16)

## Corpus Check
- Corpus is ~14,845 words - fits in a single context window. You may not need a graph.

## Summary
- 268 nodes · 610 edges · 16 communities (11 shown, 5 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 22 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- LangGraph Q&A
- SQLite ledger
- Hybrid categorize
- Insights reports
- Product docs
- Ingest parse
- LLM providers
- Notifications inbox
- Dashboard charts
- Vault encryption
- Caveman agent rules
- Env resolution
- Package init
- Transaction split
- Tax year report
- Package metadata

## God Nodes (most connected - your core abstractions)
1. `connect()` - 36 edges
2. `refresh_inbox()` - 16 edges
3. `complete()` - 12 edges
4. `anomalies()` - 11 edges
5. `snapshot()` - 11 edges
6. `alerts()` - 10 edges
7. `weekly_digest()` - 10 edges
8. `month_bounds()` - 10 edges
9. `parse_file()` - 9 edges
10. `month_compare()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `Hybrid categories` --semantically_similar_to--> `Categorize pipeline`  [INFERRED] [semantically similar]
  README.md → ARCHITECTURE.md
- `LangGraph chat` --semantically_similar_to--> `plan fetch brief reply`  [INFERRED] [semantically similar]
  README.md → ARCHITECTURE.md
- `data/finance.db tables` --semantically_similar_to--> `SQLite ledger`  [INFERRED] [semantically similar]
  docs/technical.md → README.md
- `PFENC1 vault` --semantically_similar_to--> `Fernet passphrase lock`  [INFERRED] [semantically similar]
  ARCHITECTURE.md → README.md
- `Categorize pipeline` --semantically_similar_to--> `Categorize order`  [INFERRED] [semantically similar]
  ARCHITECTURE.md → docs/technical.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Ingest categorize store** — docs_how_to_use_ingest, readme_hybrid_categories, readme_sqlite_ledger [INFERRED 0.85]
- **Privacy lock export local-only** — readme_local_only, architecture_vault, docs_how_to_use_export_lock [INFERRED 0.85]
- **Cloud and local providers** — readme_ollama, readme_openai, readme_agnes, readme_google [EXTRACTED 1.00]

## Communities (16 total, 5 thin omitted)

### Community 0 - "LangGraph Q&A"
Cohesion: 0.12
Nodes (36): AgentState, ask(), _brief(), build_graph(), _fetch(), _history_text(), _plan(), Any (+28 more)

### Community 1 - "SQLite ledger"
Cohesion: 0.12
Nodes (37): Connection, append_message(), clear_messages(), connect(), date_span(), export_snapshot(), export_zip(), get_setting() (+29 more)

### Community 2 - "Hybrid categorize"
Cohesion: 0.12
Nodes (26): apply_learned(), apply_rules(), assign_category(), categorize_hybrid(), categorize_with_llm(), Any, Rule-first categories; user rules and corrections beat builtins; LLM last., Learned tags already on rows. Local model first, API only for leftovers. (+18 more)

### Community 3 - "Insights reports"
Cohesion: 0.18
Nodes (27): anomalies(), budget_status(), _fence(), in_range(), income_of(), month_bounds(), month_compare(), Any (+19 more)

### Community 4 - "Product docs"
Cohesion: 0.07
Nodes (28): finance_agent package, Categorize pipeline, Single-process modular monolith, plan fetch brief reply, notify.refresh_inbox, streamlit_app.py UI, PFENC1 vault, Learn from corrections (+20 more)

### Community 5 - "Ingest parse"
Cohesion: 0.18
Nodes (20): DataFrame, _from_llm(), _from_loose_text(), _from_table(), _norm(), _parse_amount(), _parse_date(), parse_file() (+12 more)

### Community 6 - "LLM providers"
Cohesion: 0.16
Nodes (17): env(), Env and provider settings. Keys come from the environment only., complete(), _google(), _image_mime(), list_ollama_models(), missing_key(), models_for() (+9 more)

### Community 7 - "Notifications inbox"
Cohesion: 0.22
Nodes (17): add_notification(), date, week_bounds(), bill_reminders(), _goal_notes(), next_bill_date(), Any, date (+9 more)

### Community 8 - "Dashboard charts"
Cohesion: 0.26
Nodes (15): cancel_suggestions(), cashflow_forecast(), income_expense_series(), lifestyle_inflation(), Any, date, Phase 5 dashboard series: charts, forecast, inflation, cancel suggestions., savings_rate_series() (+7 more)

### Community 9 - "Vault encryption"
Cohesion: 0.26
Nodes (12): decrypt_bytes(), encrypt_bytes(), _fernet_key(), is_locked(), lock_db(), Optional at-rest lock for the SQLite file. Passphrase never stored., unlock_db(), MonkeyPatch (+4 more)

### Community 10 - "Caveman agent rules"
Cohesion: 0.40
Nodes (5): Caveman agent style, Cline caveman rules, Copilot caveman instructions, OpenCode AGENTS, Windsurf caveman rules

## Knowledge Gaps
- **18 isolated node(s):** `finance-agent`, `OpenAI gpt-5.6-luna terra`, `Agnes 2.5 flash`, `Google Gemini models`, `plan fetch brief reply` (+13 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `connect()` connect `SQLite ledger` to `LangGraph Q&A`, `Hybrid categorize`, `Notifications inbox`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Why does `refresh_inbox()` connect `Notifications inbox` to `LangGraph Q&A`, `SQLite ledger`, `Insights reports`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Why does `complete()` connect `LLM providers` to `LangGraph Q&A`, `SQLite ledger`, `Hybrid categorize`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `complete()` (e.g. with `categorize_with_llm()` and `test_local_only_blocks_cloud()`) actually correct?**
  _`complete()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `finance-agent`, `OpenAI gpt-5.6-luna terra`, `Agnes 2.5 flash` to the rest of the system?**
  _18 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `LangGraph Q&A` be split into smaller, more focused modules?**
  _Cohesion score 0.11605937921727395 - nodes in this community are weakly interconnected._
- **Should `SQLite ledger` be split into smaller, more focused modules?**
  _Cohesion score 0.11948790896159317 - nodes in this community are weakly interconnected._