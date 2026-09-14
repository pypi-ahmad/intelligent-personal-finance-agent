"""LangGraph Q&A over stored transactions.

Four-node pipeline: plan (LLM turns the question into search filters) ->
fetch (db.search over those filters) -> brief (adds insights.snapshot() +
learned corrections as context) -> reply (LLM answers from that context).
See db.py for the underlying transaction store and copilot.py for the
travel/date-range heuristics used when the LLM's plan is unusable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from finance_agent.config import CATEGORIES
from finance_agent.copilot import filter_travel, infer_range, wants_travel
from finance_agent.db import search, summary
from finance_agent.ingest import parse_json_payload
from finance_agent.insights import snapshot
from finance_agent.llm import complete

PLAN_PROMPT = """Turn the user question into filters for a personal finance ledger.
Today is {today}. Use prior chat only to resolve follow-ups (e.g. "what about transport?").
Return ONLY JSON:
{{"start_date": "YYYY-MM-DD"|null, "end_date": "YYYY-MM-DD"|null,
  "category": one of {cats} or null, "text": substring or null,
  "account": account name or null, "travel": true|false, "limit": 50}}
Prior:
{history}
Question: {question}
"""

ANSWER_PROMPT = """Answer using only the transaction context, brief, and prior chat.
Be concise. Use the amounts as given. Handle follow-ups using Prior.
If context is empty, say no matching transactions.
Prior:
{history}
Question: {question}
Summary: {summary}
Brief: {brief}
Transactions: {context}
"""


class AgentState(TypedDict):
    question: str
    provider: str
    model: str
    history: str
    filters: dict[str, Any]
    context: str
    brief: str
    answer: str


def _plan(state: AgentState) -> dict[str, Any]:
    today = datetime.now(UTC).date()
    raw = complete(
        state["provider"],
        state["model"],
        PLAN_PROMPT.format(
            cats=", ".join(CATEGORIES),
            question=state["question"],
            today=today.isoformat(),
            history=state.get("history") or "(none)",
        ),
    )
    # The LLM's plan is untrusted output: if it isn't valid JSON or isn't an
    # object, fall through to an empty plan so every field below degrades to
    # its keyword-heuristic fallback (infer_range, wants_travel) instead of
    # raising.
    try:
        data = parse_json_payload(raw)
    except (ValueError, TypeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    category = data.get("category")
    if category not in CATEGORIES:
        category = None
    start = data.get("start_date") or None
    end = data.get("end_date") or None
    if not start:
        inferred_start, inferred_end = infer_range(state["question"], today)
        start, end = inferred_start, inferred_end
    travel = data.get("travel")
    if not isinstance(travel, bool):
        travel = wants_travel(state["question"])
    try:
        limit = int(data.get("limit") or 50)
    except (TypeError, ValueError):
        limit = 50
    account = data.get("account") or None
    if account is not None:
        account = str(account)
    return {
        "filters": {
            "start_date": start,
            "end_date": end,
            "category": category,
            "text": data.get("text") or None,
            "account": account,
            "travel": travel,
            "limit": limit,
        }
    }


def _fetch(state: AgentState) -> dict[str, Any]:
    filters = state["filters"]
    travel = bool(filters.get("travel"))
    # Travel matching needs "was this near a travel-tagged transaction",
    # which SQL can't express here — so for travel questions, pull a wide
    # window (ignoring category/text at the DB layer) and let
    # copilot.filter_travel() do the date-adjacency filtering in Python.
    rows = search(
        start_date=filters.get("start_date"),
        end_date=filters.get("end_date"),
        category=None if travel else filters.get("category"),
        text=None if travel else filters.get("text"),
        account=filters.get("account"),
        limit=500 if travel else filters.get("limit") or 50,
    )
    if travel:
        rows = filter_travel(rows, category=filters.get("category"))
    lines = [
        (
            f"{r['date']} | {r.get('merchant') or '-'} | {r['category']} | "
            f"{r['amount']} {r['currency']} | {r.get('account') or '-'} | {r['description']}"
        )
        for r in rows
    ]
    return {"context": "\n".join(lines) if lines else "(none)"}


def _brief(_state: AgentState) -> dict[str, Any]:
    from finance_agent.db import list_fewshot

    learned = list_fewshot(8)
    extra = ""
    if learned:
        extra = "\nLearned: " + "; ".join(f"{item['merchant']}={item['category']}" for item in learned)
    return {"brief": snapshot() + extra}


def _reply(state: AgentState) -> dict[str, Any]:
    answer = complete(
        state["provider"],
        state["model"],
        ANSWER_PROMPT.format(
            question=state["question"],
            summary=summary(),
            brief=state.get("brief") or "",
            context=state["context"],
            history=state.get("history") or "(none)",
        ),
    )
    return {"answer": answer}


@lru_cache(maxsize=1)  # graph is stateless/reusable — compile once per process, not per ask() call
def build_graph():
    graph = StateGraph(AgentState)  # type: ignore[invalid-argument-type]
    graph.add_node("plan", _plan)
    graph.add_node("fetch", _fetch)
    graph.add_node("brief", _brief)
    graph.add_node("reply", _reply)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "fetch")
    graph.add_edge("fetch", "brief")
    graph.add_edge("brief", "reply")
    graph.add_edge("reply", END)
    return graph.compile()


def _history_text(history: list[dict[str, str]] | None) -> str:
    if not history:
        return "(none)"
    # Cap at the last 8 turns to keep the plan/answer prompts within a
    # reasonable size budget; older turns are dropped, not summarized.
    lines = [f"{item.get('role', '?')}: {item.get('content', '')}" for item in history[-8:]]
    return "\n".join(lines) or "(none)"


def ask(
    question: str,
    provider: str,
    model: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    result = build_graph().invoke(
        {
            "question": question,
            "provider": provider,
            "model": model,
            "history": _history_text(history),
            "filters": {},
            "context": "",
            "brief": "",
            "answer": "",
        }
    )
    return result["answer"]
