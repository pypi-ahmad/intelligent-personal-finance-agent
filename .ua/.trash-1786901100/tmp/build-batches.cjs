#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const SUMMARIES = {
  "streamlit_app.py": "Streamlit UI: unlock gate, Local-only sidebar, eight tabs, ingest and chat wiring.",
  "src/finance_agent/__init__.py": "Package marker. Phase 8 personal finance agent.",
  "src/finance_agent/agent.py": "LangGraph Q&A: plan filters, fetch rows, brief snapshot, reply.",
  "src/finance_agent/config.py": "Paths, provider model IDs, CATEGORIES, env() from process then HKCU.",
  "src/finance_agent/db.py": "SQLite connect, schema, migrate, CRUD, export zip, wipe, notifications.",
  "src/finance_agent/llm.py": "complete() facade for Ollama, OpenAI, Agnes, Google; Local-only gate.",
  "src/finance_agent/vault.py": "PFENC1 + Fernet lock/unlock of finance.db. Passphrase not stored.",
  "src/finance_agent/ingest.py": "Parse CSV, Excel, PDF, images into row dicts plus merchant.",
  "src/finance_agent/categorize.py": "User rules, corrections, builtins, then hybrid leftover LLM fill.",
  "src/finance_agent/merchants.py": "Merchant alias map and normalize_merchant / merchant_key.",
  "src/finance_agent/insights.py": "Month compare, MAD anomalies, budgets, snapshot text.",
  "src/finance_agent/copilot.py": "Travel window, recurring, net worth, alerts, weekly digest.",
  "src/finance_agent/dashboard.py": "Chart series, 30/60 forecast, inflation, cancel suggestions.",
  "src/finance_agent/notify.py": "On-open inbox: Monday digest, bills, anomalies, goals.",
  "src/finance_agent/reports.py": "Month, week, and tax-year Markdown plus PDF.",
  "README.md": "Project overview, clone/run, models, community links, data disclaimer.",
  "ARCHITECTURE.md": "On-disk architecture snapshot of the modular monolith.",
  "CONTRIBUTING.md": "How to set up, test, and send PRs. No donations.",
  "DISCLAIMER.md": "User owns all processed data; not financial advice.",
  "SECURITY.md": "How to report vulnerabilities privately.",
  "SUPPORT.md": "Self-help and community support. No paid support.",
  "Project_Architecture_Blueprint.md": "Comprehensive architecture blueprint and ADRs.",
  "docs/how-to-use.md": "How to start, set keys, use tabs, lock, and export.",
  "docs/technical.md": "Technical reference for modules, env, and storage.",
  "pyproject.toml": "uv project: deps, ruff, ty, MIT license.",
  ".env.example": "Template for user-owned API keys. Not committed secrets.",
  ".streamlit/config.toml": "Light and dark theme. Usage stats off.",
  "run.cmd": "Windows launcher: uv, .venv, sync, Streamlit on localhost.",
  "run.sh": "Linux launcher: uv, .venv, sync, Streamlit on localhost.",
};

const TABLES = [
  "transactions",
  "budgets",
  "accounts",
  "goals",
  "messages",
  "settings",
  "user_rules",
  "corrections",
  "notifications",
];

function fileType(cat) {
  if (cat === "docs") return "document";
  if (cat === "config") return "config";
  return "file";
}

function fileId(cat, p) {
  const t = fileType(cat);
  return `${t}:${p}`;
}

function complexity(lines, fnCount) {
  if (lines >= 250 || fnCount >= 20) return "complex";
  if (lines >= 80 || fnCount >= 8) return "moderate";
  return "simple";
}

function tagsFor(p, cat) {
  const tags = [];
  if (p.startsWith("tests/")) tags.push("test");
  if (p === "streamlit_app.py" || p === "README.md") tags.push("entry-point");
  if (p.includes("db.py")) tags.push("data-model", "service");
  if (p.includes("llm.py") || p.includes("agent.py")) tags.push("service");
  if (p.includes("vault.py") || p === "SECURITY.md") tags.push("security");
  if (cat === "docs") tags.push("documentation");
  if (cat === "config") tags.push("configuration");
  if (cat === "script") tags.push("entry-point");
  if (p.includes("ingest") || p.includes("categorize")) tags.push("service");
  if (tags.length < 3) tags.push("utility");
  while (tags.length < 3) tags.push("untagged");
  return [...new Set(tags)].slice(0, 5);
}

function summaryFor(p, cat, extract) {
  if (SUMMARIES[p]) return SUMMARIES[p];
  if (p.startsWith("tests/")) return `Pytest coverage for ${path.basename(p, ".py")}.`;
  if (p.includes("caveman") || p.includes("AGENTS") || p.includes("copilot-instructions"))
    return "Agent style rules for this checkout.";
  if (p.includes("ISSUE_TEMPLATE") || p.includes("PULL_REQUEST"))
    return "GitHub community template.";
  if (p.includes("archify")) return "Archify architecture diagram artifact.";
  const n = (extract.functions || []).length;
  return `${cat} file with ${extract.totalLines || 0} lines` + (n ? ` and ${n} functions.` : ".");
}

function buildBatch(idx) {
  const batches = JSON.parse(fs.readFileSync(".ua/intermediate/batches.json", "utf8"));
  const batch = batches.batches.find((b) => b.batchIndex === idx);
  const extract = JSON.parse(fs.readFileSync(`.ua/tmp/ua-file-extract-results-${idx}.json`, "utf8"));
  const byPath = Object.fromEntries((extract.results || []).map((r) => [r.path, r]));
  const importData = batch.batchImportData || {};
  const nodes = [];
  const edges = [];
  const seen = new Set();

  function addNode(n) {
    if (seen.has(n.id)) return;
    seen.add(n.id);
    if (!n.tags || !n.tags.length) n.tags = ["untagged"];
    if (!n.summary) n.summary = "No summary available";
    nodes.push(n);
  }

  for (const f of batch.files) {
    const ex = byPath[f.path] || {
      functions: [],
      classes: [],
      callGraph: [],
      totalLines: f.sizeLines,
    };
    const cat = f.fileCategory;
    const id = fileId(cat, f.path);
    addNode({
      id,
      type: fileType(cat),
      name: path.posix.basename(f.path.replace(/\\/g, "/")),
      filePath: f.path,
      summary: summaryFor(f.path, cat, ex),
      tags: tagsFor(f.path, cat),
      complexity: complexity(ex.totalLines || f.sizeLines || 0, (ex.functions || []).length),
    });

    for (const fn of ex.functions || []) {
      const span = (fn.endLine || fn.startLine || 0) - (fn.startLine || 0) + 1;
      if (span < 10 && !(ex.exports || []).some((e) => e.name === fn.name)) continue;
      const fid = `function:${f.path}:${fn.name}`;
      addNode({
        id: fid,
        type: "function",
        name: fn.name,
        filePath: f.path,
        summary: `${fn.name}() in ${f.path}`,
        tags: ["utility"],
        complexity: span >= 40 ? "complex" : span >= 15 ? "moderate" : "simple",
      });
      edges.push({
        source: id,
        target: fid,
        type: "contains",
        direction: "forward",
        weight: 1.0,
      });
    }

    for (const cls of ex.classes || []) {
      const cid = `class:${f.path}:${cls.name}`;
      addNode({
        id: cid,
        type: "class",
        name: cls.name,
        filePath: f.path,
        summary: `${cls.name} in ${f.path}`,
        tags: ["type-definition"],
        complexity: "simple",
      });
      edges.push({
        source: id,
        target: cid,
        type: "contains",
        direction: "forward",
        weight: 1.0,
      });
    }

    const imports = importData[f.path] || [];
    for (const target of imports) {
      edges.push({
        source: `file:${f.path}`,
        target: `file:${target}`,
        type: "imports",
        direction: "forward",
        weight: 0.7,
      });
    }

    if (f.path === "src/finance_agent/db.py") {
      for (const t of TABLES) {
        const tid = `table:${f.path}:${t}`;
        addNode({
          id: tid,
          type: "table",
          name: t,
          filePath: f.path,
          summary: `SQLite table ${t} in finance.db`,
          tags: ["database", "data-model"],
          complexity: "simple",
        });
        edges.push({
          source: id,
          target: tid,
          type: "defines_schema",
          direction: "forward",
          weight: 0.8,
        });
      }
    }

    if (f.path.startsWith("tests/")) {
      const prod = (importData[f.path] || []).filter((p) => p.startsWith("src/"));
      for (const p of prod) {
        edges.push({
          source: `file:${p}`,
          target: id,
          type: "tested_by",
          direction: "forward",
          weight: 0.5,
        });
      }
    }

    if (cat === "docs") {
      const targets = ["streamlit_app.py", "src/finance_agent/db.py", "src/finance_agent/agent.py"];
      for (const t of targets) {
        edges.push({
          source: id,
          target: `file:${t}`,
          type: "documents",
          direction: "forward",
          weight: 0.5,
        });
      }
    }

    if (f.path === "pyproject.toml" || f.path === ".streamlit/config.toml" || f.path === ".env.example") {
      edges.push({
        source: id,
        target: "file:streamlit_app.py",
        type: "configures",
        direction: "forward",
        weight: 0.6,
      });
    }

    if (f.path === "run.cmd" || f.path === "run.sh") {
      edges.push({
        source: id,
        target: "file:streamlit_app.py",
        type: "deploys",
        direction: "forward",
        weight: 0.7,
      });
    }
  }

  const out = { nodes, edges };
  fs.writeFileSync(`.ua/intermediate/batch-${idx}.json`, JSON.stringify(out, null, 2));
  console.log(`batch ${idx}: ${nodes.length} nodes, ${edges.length} edges`);
}

for (let i = 1; i <= 5; i++) buildBatch(i);
