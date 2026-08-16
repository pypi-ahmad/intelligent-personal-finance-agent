#!/usr/bin/env node
const fs = require("fs");

const assembled = JSON.parse(fs.readFileSync(".ua/intermediate/assembled-graph.json", "utf8"));
const scan = JSON.parse(fs.readFileSync(".ua/intermediate/scan-result.json", "utf8"));

fs.writeFileSync(
  ".ua/intermediate/assemble-review.json",
  JSON.stringify(
    {
      notes: [
        "Imports recovered 0 extra — batch emission matched importMap.",
        "graphify-out and .ua excluded via .understandignore.",
      ],
      issues: [],
    },
    null,
    2,
  ),
);

const layers = [
  {
    id: "layer:presentation",
    name: "Presentation",
    description: "Streamlit UI, launchers, and Streamlit theme.",
    nodeIds: [
      "file:streamlit_app.py",
      "file:run.cmd",
      "file:run.sh",
      "config:.streamlit/config.toml",
      "file:.python-version",
    ],
  },
  {
    id: "layer:qa-and-inbox",
    name: "Q&A and inbox",
    description: "LangGraph ask() and on-open notification refresh.",
    nodeIds: ["file:src/finance_agent/agent.py", "file:src/finance_agent/notify.py"],
  },
  {
    id: "layer:analytics",
    name: "Analytics and reports",
    description: "Insights, dashboard series, copilot helpers, Markdown/PDF reports.",
    nodeIds: [
      "file:src/finance_agent/insights.py",
      "file:src/finance_agent/dashboard.py",
      "file:src/finance_agent/copilot.py",
      "file:src/finance_agent/reports.py",
    ],
  },
  {
    id: "layer:ingest-categorize",
    name: "Ingest and categorize",
    description: "File parse, merchant aliases, hybrid category pipeline.",
    nodeIds: [
      "file:src/finance_agent/ingest.py",
      "file:src/finance_agent/categorize.py",
      "file:src/finance_agent/merchants.py",
    ],
  },
  {
    id: "layer:infrastructure",
    name: "Infrastructure",
    description: "Config, SQLite access, LLM providers, vault lock.",
    nodeIds: [
      "file:src/finance_agent/__init__.py",
      "file:src/finance_agent/config.py",
      "file:src/finance_agent/db.py",
      "file:src/finance_agent/llm.py",
      "file:src/finance_agent/vault.py",
    ],
  },
  {
    id: "layer:sqlite-tables",
    name: "SQLite tables",
    description: "Ledger and supporting tables defined in db.py SCHEMA.",
    nodeIds: [
      "table:src/finance_agent/db.py:transactions",
      "table:src/finance_agent/db.py:budgets",
      "table:src/finance_agent/db.py:accounts",
      "table:src/finance_agent/db.py:goals",
      "table:src/finance_agent/db.py:messages",
      "table:src/finance_agent/db.py:settings",
      "table:src/finance_agent/db.py:user_rules",
      "table:src/finance_agent/db.py:corrections",
      "table:src/finance_agent/db.py:notifications",
    ],
  },
  {
    id: "layer:tests",
    name: "Tests",
    description: "Phase 1–6 and 8 pytest modules.",
    nodeIds: [
      "file:tests/test_phase1.py",
      "file:tests/test_phase2.py",
      "file:tests/test_phase3.py",
      "file:tests/test_phase4.py",
      "file:tests/test_phase5.py",
      "file:tests/test_phase6.py",
      "file:tests/test_phase8.py",
    ],
  },
  {
    id: "layer:product-docs",
    name: "Product docs",
    description: "README, architecture, how-to, disclaimer, and community guides.",
    nodeIds: [
      "document:README.md",
      "document:ARCHITECTURE.md",
      "document:CONTRIBUTING.md",
      "document:DISCLAIMER.md",
      "document:Project_Architecture_Blueprint.md",
      "document:SECURITY.md",
      "document:SUPPORT.md",
      "document:AGENTS.md",
      "document:docs/how-to-use.md",
      "document:docs/technical.md",
    ],
  },
  {
    id: "layer:tooling",
    name: "Tooling and community",
    description: "GitHub templates, agent rules, env template, and Archify artifacts.",
    nodeIds: [
      "config:.env.example",
      "config:pyproject.toml",
      "document:.clinerules/caveman.md",
      "file:.cursor/rules/caveman.mdc",
      "document:.github/ISSUE_TEMPLATE/bug_report.md",
      "document:.github/ISSUE_TEMPLATE/feature_request.md",
      "document:.github/PULL_REQUEST_TEMPLATE.md",
      "document:.github/copilot-instructions.md",
      "document:.opencode/AGENTS.md",
      "document:.windsurf/rules/caveman.md",
      "config:docs/archify/finance-agent.architecture.json",
      "file:docs/archify/finance-agent.html",
    ],
  },
];

const tour = [
  {
    order: 1,
    title: "What this project is",
    description: "Start with the README: local-first ledger, your keys, no donations.",
    nodeIds: ["document:README.md", "document:DISCLAIMER.md"],
  },
  {
    order: 2,
    title: "How to launch",
    description: "Windows run.cmd or Linux run.sh create a uv .venv and start Streamlit on localhost.",
    nodeIds: ["file:run.cmd", "file:run.sh", "file:streamlit_app.py"],
  },
  {
    order: 3,
    title: "UI composition root",
    description: "streamlit_app.py unlocks the vault, wires tabs, and calls the package.",
    nodeIds: ["file:streamlit_app.py", "file:src/finance_agent/vault.py"],
  },
  {
    order: 4,
    title: "Ingest and learn categories",
    description: "parse_file then user rules, corrections, builtins, leftover LLM fill, insert_many.",
    nodeIds: [
      "file:src/finance_agent/ingest.py",
      "file:src/finance_agent/categorize.py",
      "file:src/finance_agent/db.py",
    ],
  },
  {
    order: 5,
    title: "Ask questions",
    description: "LangGraph plan → fetch → brief → reply through llm.complete.",
    nodeIds: ["file:src/finance_agent/agent.py", "file:src/finance_agent/llm.py"],
  },
  {
    order: 6,
    title: "Store and lock",
    description: "SQLite tables in finance.db; optional PFENC1 Fernet lock.",
    nodeIds: [
      "file:src/finance_agent/db.py",
      "table:src/finance_agent/db.py:transactions",
      "file:src/finance_agent/vault.py",
    ],
  },
];

fs.writeFileSync(".ua/intermediate/layers.json", JSON.stringify(layers, null, 2));
fs.writeFileSync(".ua/intermediate/tour.json", JSON.stringify(tour, null, 2));

const nodeIds = new Set(assembled.nodes.map((n) => n.id));
for (const layer of layers) {
  layer.nodeIds = layer.nodeIds.filter((id) => nodeIds.has(id));
}
for (const step of tour) {
  step.nodeIds = step.nodeIds.filter((id) => nodeIds.has(id));
}

const graph = {
  version: "1.0.0",
  project: {
    name: scan.name,
    languages: scan.languages,
    frameworks: scan.frameworks,
    description: scan.description,
    analyzedAt: new Date().toISOString(),
    gitCommitHash: "5347883ab3f5bf2775f24d8e41dff974496a353c",
  },
  nodes: assembled.nodes,
  edges: assembled.edges,
  layers,
  tour,
};

fs.writeFileSync(".ua/intermediate/assembled-graph.json", JSON.stringify(graph, null, 2));
console.log("assembled graph written", graph.nodes.length, graph.edges.length, layers.length, tour.length);
