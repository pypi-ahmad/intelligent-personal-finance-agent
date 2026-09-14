"""Single-page Streamlit UI for the finance agent.

Streamlit reruns this whole script top-to-bottom on every widget
interaction; st.session_state is the only state that survives a rerun.
Business logic lives in the finance_agent package (db.py for storage,
agent.py for chat, ingest.py for statement parsing) — this file wires
those into widgets and should stay presentation-only.
"""

from contextlib import suppress
from datetime import UTC, date, datetime

import altair as alt
import streamlit as st

from finance_agent.agent import ask
from finance_agent.categorize import apply_learned, categorize_hybrid
from finance_agent.config import ACCOUNT_KINDS, CATEGORIES, GOAL_KINDS, PROVIDERS
from finance_agent.copilot import (
    alerts,
    detect_recurring,
    goal_progress,
    net_worth,
    weekly_digest,
)
from finance_agent.dashboard import (
    cancel_suggestions,
    cashflow_forecast,
    income_expense_series,
    lifestyle_inflation,
    savings_rate_series,
    spend_by_month_category,
    top_merchants,
)
from finance_agent.db import (
    append_message,
    clear_messages,
    date_span,
    export_zip,
    insert_many,
    is_local_only,
    list_accounts,
    list_budgets,
    list_goals,
    list_messages,
    list_notifications,
    list_transactions,
    list_user_rules,
    mark_all_notifications_read,
    mark_notification_read,
    privacy_stats,
    search,
    set_local_only,
    split_transaction,
    summary,
    unread_count,
    update_account,
    update_category,
    upsert_account,
    upsert_budget,
    upsert_goal,
    upsert_user_rule,
    wipe_all,
    wipe_ledger,
)
from finance_agent.ingest import parse_file
from finance_agent.insights import (
    anomalies,
    budget_status,
    month_bounds,
    month_compare,
    monthly_series,
    top_categories,
    week_bounds,
    weekly_series,
)
from finance_agent.llm import complete, list_ollama_models, missing_key, models_for
from finance_agent.notify import refresh_inbox
from finance_agent.reports import month_markdown, report_pdf, tax_year_markdown, week_markdown
from finance_agent.vault import is_locked, lock_db, unlock_db

st.set_page_config(
    page_title="Personal finance agent",
    page_icon=":material/account_balance:",
    layout="wide",
    initial_sidebar_state="auto",
)

st.session_state.setdefault("messages", [])
st.session_state.setdefault("last_error", "")


# Must run before any db.py access: while locked, DB_PATH doesn't exist and
# db.connect() would just create an empty database over the encrypted one.
if is_locked():
    st.title("Unlock database")
    st.caption("Your ledger is encrypted on disk. Enter the passphrase.")
    phrase = st.text_input("Passphrase", type="password", key="unlock_pw")
    if st.button("Unlock", type="primary", icon=":material/lock_open:"):
        try:
            unlock_db(phrase)
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    st.stop()

if not st.session_state.get("mem_loaded"):
    st.session_state.messages = list_messages()
    st.session_state.mem_loaded = True


def _today() -> date:
    return datetime.now(UTC).date()


def _call(provider_name: str, model_name: str, prompt: str) -> str:
    return complete(provider_name, model_name, prompt)


def _hybrid_completes(provider: str, model: str, key_missing: str | None):
    # provider/model/local_models[0] are captured as default-argument values
    # (_p, _m), not by closure reference, so each returned function keeps
    # the value it had at definition time even though `provider`/`model`
    # are ordinary script-level names that could otherwise be reused later.
    local_fn = None
    api_fn = None
    if provider == "Ollama" and model:

        def local_fn(prompt: str, _m: str = model) -> str:
            return _call("Ollama", _m, prompt)
    else:
        local_models = list_ollama_models()
        if local_models:

            def local_fn(prompt: str, _m: str = local_models[0]) -> str:
                return _call("Ollama", _m, prompt)

        if model and not key_missing and not is_local_only():

            def api_fn(prompt: str, _p: str = provider, _m: str = model) -> str:
                return _call(_p, _m, prompt)
    return local_fn, api_fn


def _remember(role: str, content: str) -> None:
    st.session_state.messages.append({"role": role, "content": content})
    append_message(role, content)


with st.sidebar:
    st.subheader("Mode")
    local_on = st.toggle("Local-only", value=is_local_only(), key="local_toggle")
    if local_on != is_local_only():
        set_local_only(on=local_on)
        st.rerun()
    if local_on:
        st.caption("Cloud APIs off. Ollama only.")

    st.subheader("Model")
    provider_opts = ("Ollama",) if local_on else PROVIDERS
    provider = st.selectbox("Provider", provider_opts, key=f"provider_{int(local_on)}")
    models = models_for(provider)
    if not models:
        st.warning("No models found. Start Ollama or check API keys.")
        model = ""
    else:
        model = st.selectbox("Model", models, key=f"model_{provider}")
        if provider == "OpenAI":
            st.caption("gpt-5.6-luna · gpt-5.6-terra · effort medium")
        elif provider == "Agnes AI":
            st.caption("agnes-2.5-flash")
        elif provider == "Google":
            st.caption("gemini-3.5-flash-lite · gemini-3.7-flash")
        elif provider == "Ollama":
            st.caption(f"{len(models)} local model(s)")
    key_missing = missing_key(provider)
    if key_missing:
        st.error(f"Missing {key_missing} in environment")

    st.subheader("Upload statements")
    uploads = st.file_uploader(
        "Bank, card, UPI, or expense sheets",
        type=["pdf", "csv", "xlsx", "xls", "png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="uploads",
    )
    use_llm_cats = st.checkbox("Hybrid leftover categories", value=True)
    acct_names = [a["name"] for a in list_accounts()]
    ingest_acct = st.selectbox("Assign to account", ["(none)", *acct_names], key="ingest_acct")
    ingest = st.button("Ingest files", type="primary", icon=":material/upload_file:")

st.title("Personal finance agent")
st.caption("Phase 8 — private, exportable, tax-ready. Dark/light in the app menu.")
refresh_inbox(_today())
unread = unread_count()
if unread:
    st.info(f"{unread} unread notification(s). Open Notifications.")

stats = summary()
worth = net_worth(list_accounts())
with st.container(horizontal=True):
    st.metric("Transactions", f"{stats['count']}", border=True)
    st.metric("Spent", f"{stats['spent']:.2f}", border=True)
    st.metric("Income", f"{stats['income']:.2f}", border=True)
    st.metric("Net worth", f"{worth['net']:.2f}", border=True)

if ingest:
    if not uploads:
        st.warning("Choose at least one file.")
    else:

        def llm_extract(prompt: str, image: bytes | None = None) -> str:
            if not model:
                raise ValueError("Select a model first.")
            return complete(provider, model, prompt, image=image)

        added_total = 0
        with st.status("Reading files", expanded=True) as status:
            for upload in uploads:
                st.write(upload.name)
                try:
                    rows = parse_file(upload.name, upload.getvalue(), llm_extract=llm_extract)
                    rows = apply_learned(rows)
                    if ingest_acct != "(none)":
                        for row in rows:
                            row["account"] = ingest_acct
                    if use_llm_cats:
                        local_fn, api_fn = _hybrid_completes(provider, model, key_missing)
                        if local_fn or api_fn:
                            rows = categorize_hybrid(
                                rows,
                                local_complete=local_fn,
                                api_complete=api_fn,
                            )
                    added = insert_many(rows)
                    added_total += added
                    st.write(f"{len(rows)} parsed, {added} new")
                except Exception as exc:
                    # Broad on purpose: one malformed statement (bad parse,
                    # LLM extraction failure, etc.) shouldn't abort the rest
                    # of a multi-file batch upload.
                    st.write(f"Failed: {exc}")
            status.update(label=f"Ingest done — {added_total} new rows", state="complete")
        if added_total:
            st.rerun()

dash_tab, note_tab, chat_tab, table_tab, insights_tab, plan_tab, report_tab, privacy_tab = st.tabs(
    ["Dashboard", "Notifications", "Chat", "Transactions", "Insights", "Plan", "Reports", "Privacy"],
    on_change="rerun",
)
# Each `if X_tab.open:` block below only runs while that tab is the active
# one — switching tabs reruns the script but skips the other tabs' queries
# and widgets rather than rendering all of them hidden.

if note_tab.open:
    with note_tab:
        notes = list_notifications()
        with st.container(horizontal=True):
            st.metric("Unread", f"{unread_count()}")
            if st.button("Mark all read", icon=":material/done_all:"):
                mark_all_notifications_read()
                st.rerun()
        st.subheader("Inbox")
        if not notes:
            st.caption("Nothing yet. Open the app on Monday for the weekly digest, or add transactions.")
        else:
            for note in notes:
                state = "unread" if not note["read"] else "read"
                with st.container(border=True):
                    st.markdown(f"**{note['title']}** · {note['kind']} · {state}")
                    st.write(note["body"])
                    st.caption(note["created_at"])
                    if not note["read"] and st.button("Mark read", key=f"read_{note['id']}"):
                        mark_notification_read(int(note["id"]))
                        st.rerun()
        st.subheader("Goals")
        goals = list_goals()
        if not goals:
            st.caption("No goals. Add them on Plan.")
        else:
            for goal in goals:
                ratio = goal_progress(goal)
                with st.container(border=True):
                    st.markdown(f"**{goal['name']}** ({goal['kind']})")
                    st.progress(ratio)
                    due = goal.get("deadline") or "n/a"
                    st.caption(f"{goal['current']:.2f} / {goal['target']:.2f} · due {due}")

if dash_tab.open:
    with dash_tab:
        all_rows = list_transactions(500)
        if not all_rows:
            st.info("No transactions yet. Upload a CSV or Excel sheet to start.")
        else:
            period = _today().strftime("%Y-%m")
            rec = detect_recurring(all_rows)
            f30 = cashflow_forecast(all_rows, rec, _today(), 30)
            f60 = cashflow_forecast(all_rows, rec, _today(), 60)
            with st.container(horizontal=True):
                st.metric("30-day cashflow", f"{f30['forecast']:.2f}", border=True)
                st.metric("60-day cashflow", f"{f60['forecast']:.2f}", border=True)
            infl = lifestyle_inflation(all_rows, _today())
            if infl and infl["flagged"]:
                st.warning(
                    f"Lifestyle inflation: spend up {infl['spend_change']:.0%} vs prior 3 months "
                    f"(income {infl['income_change']:.0%})."
                )
            cat_rows = spend_by_month_category(all_rows)
            ie_rows = income_expense_series(all_rows)
            save_rows = savings_rate_series(all_rows)
            merch_rows = top_merchants(all_rows)
            c1, c2 = st.columns(2)
            with c1, st.container(border=True):
                st.subheader("Monthly spend by category")
                if cat_rows:
                    chart = (
                        alt.Chart(cat_rows)
                        .mark_bar()
                        .encode(
                            x=alt.X("month:N", title="Month"),
                            y=alt.Y("spent:Q", title="Spent"),
                            color="category:N",
                            tooltip=["month", "category", "spent"],
                        )
                    )
                    st.altair_chart(chart)
            with c2, st.container(border=True):
                st.subheader("Income vs expense")
                if ie_rows:
                    chart = (
                        alt.Chart(ie_rows)
                        .mark_bar()
                        .encode(
                            x=alt.X("month:N", title="Month"),
                            y=alt.Y("amount:Q", title="Amount"),
                            color="kind:N",
                            xOffset="kind:N",
                            tooltip=["month", "kind", "amount"],
                        )
                    )
                    st.altair_chart(chart)
            c3, c4 = st.columns(2)
            with c3, st.container(border=True):
                st.subheader("Savings rate")
                if save_rows:
                    chart = (
                        alt.Chart(save_rows)
                        .mark_line(point=True)
                        .encode(
                            x=alt.X("month:N", title="Month"),
                            y=alt.Y("savings_rate:Q", title="Savings rate", axis=alt.Axis(format="%")),
                            tooltip=["month", "savings_rate"],
                        )
                    )
                    st.altair_chart(chart)
            with c4, st.container(border=True):
                st.subheader("Top merchants")
                if merch_rows:
                    chart = (
                        alt.Chart(merch_rows)
                        .mark_bar()
                        .encode(
                            x=alt.X("spent:Q", title="Spent"),
                            y=alt.Y("merchant:N", sort="-x", title="Merchant"),
                            tooltip=["merchant", "spent"],
                        )
                    )
                    st.altair_chart(chart)
            with st.container(border=True):
                st.subheader("Budget vs actual")
                status = budget_status(all_rows, list_budgets(period), period)
                if not status:
                    st.caption("No budgets this month. Set them on Plan.")
                else:
                    for item in status:
                        label = f"{item['category']}: {item['actual']:.2f} / {item['budget']:.2f}"
                        st.markdown(f"**{label}**")
                        ratio = 0.0 if item["budget"] <= 0 else min(item["actual"] / item["budget"], 1.0)
                        st.progress(ratio)
                        st.caption("Over budget" if item["over"] else f"{item['remaining']:.2f} left")
            with st.container(border=True):
                st.subheader("Subscriptions you can cancel")
                tips = cancel_suggestions(rec)
                if tips:
                    st.dataframe(tips, hide_index=True)
                    st.caption(f"Yearly if cancelled: {sum(t['yearly_savings'] for t in tips):.2f}")
                else:
                    st.caption("None detected (need 3+ similar charges).")

if chat_tab.open:
    with chat_tab:
        suggestions = {
            "What did I spend last month?": "What did I spend last month?",
            "Break down food spend": "How much did I spend on FOOD?",
            "Unusual spend": "Any unusual transactions this month?",
            "Budget status": "How am I doing against my budgets this month?",
            "Travel food last quarter": "How much did I spend on food while traveling last quarter?",
        }
        if not st.session_state.messages:
            picked = st.pills("Try asking", list(suggestions), label_visibility="collapsed")
            if picked:
                _remember("user", suggestions[picked])
                st.rerun()

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        # A submitted chat_input only has a value on the run it was
        # submitted; the answer is generated on that same run below, and
        # the exchange is also persisted to session_state/db so it survives
        # later reruns triggered by unrelated widgets. `pending` therefore
        # covers two cases: a fresh submission, or a user message from a
        # prior run that never got a reply appended (e.g. the run was
        # interrupted) — guarded by checking the message *before* it isn't
        # already an assistant reply, so an answered question isn't redone.
        prompt = st.chat_input("Ask about your transactions", submit_mode="disable")
        pending = None
        if prompt:
            pending = prompt
        elif (
            st.session_state.messages
            and st.session_state.messages[-1]["role"] == "user"
            and (len(st.session_state.messages) == 1 or st.session_state.messages[-2]["role"] != "assistant")
        ):
            pending = st.session_state.messages[-1]["content"]

        if pending:
            last = st.session_state.messages[-1] if st.session_state.messages else None
            if not last or last["content"] != pending:
                _remember("user", pending)
                with st.chat_message("user"):
                    st.write(pending)
            if not model or (key_missing and not local_on):
                answer = "Select a provider/model and set the API key first."
            else:
                prior = [m for m in st.session_state.messages if m["content"] != pending][-8:]
                with st.chat_message("assistant"):
                    with st.spinner("Looking through transactions"):
                        answer = ask(pending, provider, model, history=prior)
                    st.write(answer)
            if not (st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant"):
                _remember("assistant", answer)

if table_tab.open:
    with table_tab:
        span = date_span()
        if not span[0]:
            st.info("No transactions yet. Upload a CSV or Excel sheet to start.")
        else:
            default_start = date.fromisoformat(span[0])
            default_end = date.fromisoformat(span[1])
            picked = st.date_input(
                "Date range",
                value=(default_start, default_end),
                key="tx_dates",
            )
            start_s = end_s = None
            with suppress(TypeError, IndexError, AttributeError):
                start_s, end_s = picked[0].isoformat(), picked[1].isoformat()
            with st.container(horizontal=True):
                cat = st.selectbox("Category", ["All", *CATEGORIES], key="tx_cat")
                acct = st.selectbox("Account", ["All", *acct_names], key="tx_acct")
                query = st.text_input("Search description", key="tx_q")
            rows = search(
                start_date=start_s,
                end_date=end_s,
                category=None if cat == "All" else cat,
                text=query.strip() or None,
                account=None if acct == "All" else acct,
                limit=500,
            )
            if not rows:
                st.info("No rows match these filters.")
            else:
                edited = st.data_editor(
                    rows,
                    hide_index=True,
                    disabled=["id", "date", "description", "amount", "currency", "source_file", "merchant"],
                    column_config={
                        "id": st.column_config.NumberColumn("Id", format="%d"),
                        "date": st.column_config.TextColumn("Date"),
                        "description": st.column_config.TextColumn("Description", pinned=True),
                        "merchant": st.column_config.TextColumn("Merchant"),
                        "amount": st.column_config.NumberColumn("Amount", format="%.2f"),
                        "currency": st.column_config.TextColumn("Currency"),
                        "category": st.column_config.SelectboxColumn("Category", options=list(CATEGORIES)),
                        "source_file": st.column_config.TextColumn("Source"),
                        "account": st.column_config.SelectboxColumn(
                            "Account",
                            options=["", *acct_names],
                        ),
                        "parent_id": None,
                    },
                    key=f"tx_editor_{start_s}_{end_s}_{cat}_{acct}_{query}",
                    num_rows="fixed",
                )
                # st.data_editor can return a pandas DataFrame or a plain
                # list of dicts depending on the environment; branch on
                # shape to read edited columns either way.
                if hasattr(edited, "columns"):
                    new_cats = edited["category"]
                    new_accts = edited["account"]
                else:
                    new_cats = [r["category"] for r in edited]
                    new_accts = [r.get("account") for r in edited]
                # Pairing by position relies on num_rows="fixed" and the id
                # column being disabled, so `edited` is always the same rows
                # as `rows` in the same order — no row identity is checked.
                for orig, new_cat, new_acct in zip(rows, new_cats, new_accts, strict=True):
                    if new_cat != orig["category"] and new_cat in CATEGORIES:
                        update_category(int(orig["id"]), new_cat)
                    old_acct = orig.get("account") or ""
                    if str(new_acct or "") != str(old_acct):
                        update_account(int(orig["id"]), new_acct or None)
                st.caption("Category edits are stored and reused as few-shot examples.")
                with st.form("split_form"):
                    st.markdown("**Split a transaction**")
                    sid = st.number_input("Transaction id", min_value=1, step=1, key="split_id")
                    a1 = st.number_input("Part 1 amount", step=1.0, key="split_a1")
                    c1 = st.selectbox("Part 1 category", CATEGORIES, key="split_c1")
                    a2 = st.number_input("Part 2 amount", step=1.0, key="split_a2")
                    c2 = st.selectbox("Part 2 category", CATEGORIES, key="split_c2")
                    split_go = st.form_submit_button("Split", icon=":material/call_split:")
                if split_go:
                    try:
                        n = split_transaction(int(sid), [
                            {"amount": float(a1), "category": c1},
                            {"amount": float(a2), "category": c2},
                        ])
                        st.success(f"Split into {n} rows")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

if insights_tab.open:
    with insights_tab:
        all_rows = list_transactions(500)
        if not all_rows:
            st.info("No transactions yet.")
        else:
            period = _today().strftime("%Y-%m")
            start, end = month_bounds(period)
            month_rows = [r for r in all_rows if start <= r["date"] <= end]
            compare = month_compare(all_rows, period)
            prev_abs = abs(compare["prev_spent"])
            this_abs = abs(compare["spent"])
            delta_pct = None if prev_abs == 0 else (this_abs - prev_abs) / prev_abs
            delta_label = None if delta_pct is None else f"{delta_pct:.0%}"
            with st.container(horizontal=True):
                st.metric("This month spent", f"{compare['spent']:.2f}", delta=delta_label, border=True)
                st.metric("Last month spent", f"{compare['prev_spent']:.2f}", border=True)
                st.metric("This month income", f"{compare['income']:.2f}", border=True)
            tops = top_categories(month_rows)
            series = monthly_series(all_rows)
            weeks = weekly_series(all_rows)
            c1, c2 = st.columns(2)
            with c1, st.container(border=True):
                st.subheader("Top categories this month")
                if tops:
                    st.bar_chart(tops, x="category", y="spent")
                else:
                    st.caption("No spend this month.")
            with c2, st.container(border=True):
                st.subheader("Monthly spend")
                if series:
                    st.line_chart(series, x="month", y="spent")
            if weeks:
                with st.container(border=True):
                    st.subheader("Weekly spend")
                    st.bar_chart(weeks, x="week", y="spent")
            flags = anomalies(month_rows)
            notes = alerts(
                rows=all_rows,
                budgets=list_budgets(period),
                period=period,
                goals=list_goals(),
                today=_today(),
            )
            with st.container(border=True):
                st.subheader("Alerts")
                if notes:
                    for note in notes:
                        st.warning(note)
                else:
                    st.caption("No alerts.")
            recurring = detect_recurring(all_rows)
            with st.container(border=True):
                st.subheader("Recurring payments")
                if recurring:
                    st.dataframe(recurring, hide_index=True)
                else:
                    st.caption("None detected (need 3+ similar expenses).")
            with st.container(border=True):
                st.subheader("Unusual transactions")
                if flags:
                    st.dataframe(flags, hide_index=True)
                else:
                    st.caption("None flagged this month.")
            digest = weekly_digest(
                rows=all_rows,
                budgets=list_budgets(period),
                period=period,
                goals=list_goals(),
                accounts=list_accounts(),
                today=_today(),
            )
            st.download_button(
                "Download weekly digest",
                data=digest,
                file_name=f"digest-{_today().isoformat()}.md",
                mime="text/markdown",
                icon=":material/newspaper:",
            )

if plan_tab.open:
    with plan_tab:
        period = st.text_input("Month", value=_today().strftime("%Y-%m"), key="budget_period")
        with st.form("budget_form"):
            bcat = st.selectbox("Category", CATEGORIES, key="budget_cat")
            bamt = st.number_input("Monthly budget", min_value=0.0, step=100.0, key="budget_amt")
            saved = st.form_submit_button("Save budget", icon=":material/savings:")
        if saved:
            try:
                upsert_budget(bcat, period.strip(), float(bamt))
                st.success(f"Saved {bcat} for {period.strip()}")
            except ValueError as exc:
                st.error(str(exc))
        rows = list_transactions(500)
        status = budget_status(rows, list_budgets(period.strip()), period.strip())
        if not status:
            st.info("No budgets for this month yet.")
        else:
            for item in status:
                with st.container(border=True):
                    label = f"{item['category']}: {item['actual']:.2f} / {item['budget']:.2f}"
                    st.markdown(f"**{label}**")
                    ratio = 0.0 if item["budget"] <= 0 else min(item["actual"] / item["budget"], 1.0)
                    st.progress(ratio)
                    leftover = f"{item['remaining']:.2f} left"
                    st.caption("Over budget" if item["over"] else leftover)

        st.subheader("Custom category rules")
        with st.form("rule_form"):
            needle = st.text_input("If description contains")
            rcat = st.selectbox("Then category", CATEGORIES, key="rule_cat")
            rule_go = st.form_submit_button("Save rule", icon=":material/rule:")
        if rule_go:
            try:
                upsert_user_rule(needle, rcat)
                st.success(f"Rule: {needle} → {rcat}")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        rules = list_user_rules()
        if rules:
            st.dataframe(rules, hide_index=True)

        st.subheader("Accounts")
        with st.form("account_form"):
            aname = st.text_input("Account name")
            akind = st.selectbox("Kind", ACCOUNT_KINDS)
            abal = st.number_input("Balance", step=100.0)
            asave = st.form_submit_button("Save account", icon=":material/account_balance:")
        if asave:
            try:
                upsert_account(aname, akind, float(abal))
                st.success(f"Saved {aname}")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        accounts = list_accounts()
        if accounts:
            st.dataframe(accounts, hide_index=True)
            nw = net_worth(accounts)
            st.caption(f"Assets {nw['assets']:.2f} — liabilities {nw['liabilities']:.2f} = {nw['net']:.2f}")

        st.subheader("Goals")
        with st.form("goal_form"):
            gname = st.text_input("Goal name")
            gkind = st.selectbox("Kind", GOAL_KINDS)
            gtarget = st.number_input("Target", min_value=1.0, step=100.0)
            gcur = st.number_input("Current / paid", min_value=0.0, step=100.0)
            gdue = st.date_input("Deadline", value=_today(), key="goal_due")
            gsave = st.form_submit_button("Add goal", icon=":material/flag:")
        if gsave:
            try:
                upsert_goal(gname, gkind, float(gtarget), float(gcur), gdue.isoformat())
                st.success(f"Saved {gname}")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        for goal in list_goals():
            target = float(goal["target"])
            ratio = 0.0 if target <= 0 else min(float(goal["current"]) / target, 1.0)
            with st.container(border=True):
                st.markdown(f"**{goal['name']}** ({goal['kind']})")
                st.progress(ratio)
                st.caption(f"{goal['current']:.2f} / {goal['target']:.2f} · due {goal['deadline'] or 'n/a'}")

if report_tab.open:
    with report_tab:
        all_rows = list_transactions(500)
        if not all_rows:
            st.info("No transactions yet.")
        else:
            kind = st.segmented_control(
                "Report",
                ["Month", "Week", "Tax year"],
                key="rpt_kind",
                default="Month",
            )
            if kind == "Week":
                day = st.date_input("Week of", value=_today(), key="rpt_week")
                text = week_markdown(day, all_rows)
                stamp = week_bounds(day)[2]
            elif kind == "Tax year":
                years = sorted({int(r["date"][:4]) for r in all_rows}, reverse=True)
                year = st.selectbox("Year", years, key="rpt_year")
                text = tax_year_markdown(int(year), all_rows)
                stamp = f"tax-{year}"
            else:
                months = sorted({r["date"][:7] for r in all_rows}, reverse=True)
                today_m = _today().strftime("%Y-%m")
                if today_m not in months:
                    months.insert(0, today_m)
                period = st.selectbox("Month", months, key="rpt_month")
                text = month_markdown(period, all_rows, list_budgets(period))
                stamp = period
            st.markdown(text)
            pdf = report_pdf(text)
            with st.container(horizontal=True):
                st.download_button(
                    "Download markdown",
                    data=text,
                    file_name=f"finance-report-{stamp}.md",
                    mime="text/markdown",
                    icon=":material/markdown:",
                )
                st.download_button(
                    "Download PDF",
                    data=pdf,
                    file_name=f"finance-report-{stamp}.pdf",
                    mime="application/pdf",
                    icon=":material/picture_as_pdf:",
                )

if privacy_tab.open:
    with privacy_tab:
        stats = privacy_stats()
        st.subheader("What is stored")
        st.write(
            "Ledger is a local SQLite file (`data/finance.db`). "
            "API keys are never stored here — they come from this machine's environment. "
            "Chat, corrections, and rules stay in the same file."
        )
        st.json(stats)
        st.caption("Also: settings, notifications, user_rules, corrections.")
        st.subheader("Export")
        st.download_button(
            "Download full export (zip)",
            data=export_zip(),
            file_name="finance-export.zip",
            mime="application/zip",
            icon=":material/download:",
        )
        st.caption("Contains data.json plus transactions.csv.")
        st.subheader("Encrypt database")
        with st.form("lock_db"):
            pw1 = st.text_input("Passphrase", type="password", key="lock_pw")
            pw2 = st.text_input("Confirm passphrase", type="password", key="lock_pw2")
            lock_go = st.form_submit_button("Lock database", icon=":material/lock:")
        if lock_go:
            if pw1 != pw2 or not pw1:
                st.error("Passphrases must match and not be empty.")
            else:
                try:
                    lock_db(pw1)
                    # Forces chat history to be reloaded from disk on next
                    # unlock instead of leaving the now-hidden data's
                    # messages visible in this session's memory.
                    st.session_state.mem_loaded = False
                    st.success("Locked. Reload and unlock to continue.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        if st.button("Delete chat history", icon=":material/chat_bubble:"):
            clear_messages()
            st.session_state.messages = []
            st.rerun()
        if st.button("Delete transactions", icon=":material/table_rows:"):
            wipe_ledger()
            st.rerun()
        with st.form("wipe_all"):
            phrase = st.text_input("Type DELETE to wipe ledger, chat, budgets, accounts, goals")
            go = st.form_submit_button("Wipe all local data", icon=":material/delete:")
        # Typed-confirmation gate for an irreversible action (db.wipe_all
        # has no undo) — this is the one check standing in front of it.
        if go and phrase.strip() == "DELETE":
            wipe_all()
            st.session_state.messages = []
            st.rerun()
