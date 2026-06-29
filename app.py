"""Kanban flow metrics for a Linear team. Run: uv run streamlit run app.py

Shows the four core flow metrics (Little's Law family):
  throughput, cycle time (p50/p85), WIP, work item age.
All computed from startedAt / completedAt / state.type returned by Linear's GraphQL API.
"""
import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st

import metrics

API = "https://api.linear.app/graphql"


def gql(key, query, variables=None):
    r = requests.post(
        API,
        json={"query": query, "variables": variables or {}},
        headers={"Authorization": key, "Content-Type": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]


def fetch_issues(key, where):
    """Paginate issues matching an IssueFilter dict.
    ponytail: caps at 10 pages (2500 issues), plenty for a small team; raise if needed."""
    q = """
    query($after: String, $filter: IssueFilter) {
      issues(first: 250, after: $after, filter: $filter) {
        pageInfo { hasNextPage endCursor }
        nodes { identifier title startedAt completedAt state { name type } assignee { name } }
      }
    }"""
    nodes, after = [], None
    for _ in range(10):
        page = gql(key, q, {"after": after, "filter": where})["issues"]
        nodes += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    return nodes


@st.cache_data(ttl=300, show_spinner="Querying Linear…")
def load(key, team_id, weeks):
    since = (datetime.now(timezone.utc) - timedelta(weeks=weeks)).isoformat()
    team = {"team": {"id": {"eq": team_id}}}
    completed = fetch_issues(key, {**team, "completedAt": {"gte": since}})
    active = fetch_issues(key, {**team, "state": {"type": {"eq": "started"}}})
    return completed, active


@st.cache_data(ttl=600, show_spinner=False)
def load_teams(key):
    return gql(key, "{ teams { nodes { id name } } }")["teams"]["nodes"]


def who(i):
    return (i.get("assignee") or {}).get("name") or "Unassigned"


OR_API = "https://openrouter.ai/api/v1/chat/completions"
OR_MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")  # any slug from openrouter.ai/models
INSIGHTS_SYSTEM = (
    "You are a Kanban flow coach for a 3-engineer team. You're given today's flow metrics. "
    "Give 3-5 short, specific, actionable bullets a team could act on at standup. "
    "Ground everything in Little's Law (cycle time ≈ WIP ÷ throughput). "
    "Distinguish leading levers (WIP, work item age — act now) from lagging reports (throughput, cycle time). "
    "p85 is the Service Level Expectation; a high p85 vs p50 means a fat tail, not slow average — point at the specific aging cards. "
    "Do NOT rank people by output; per-person data is for spotting overload only. No preamble, just the bullets."
)


@st.cache_data(ttl=86400, show_spinner="Generating insights…")
def ai_insights(or_key, model, summary, day):
    r = requests.post(
        OR_API,
        headers={"Authorization": f"Bearer {or_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": [
            {"role": "system", "content": INSIGHTS_SYSTEM},
            {"role": "user", "content": summary}]},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


# ── UI ────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Kanban Flow Metrics", layout="wide")
st.title("Kanban Flow Metrics")
st.caption("cycle time ≈ WIP ÷ throughput — Little's Law")

key = os.environ.get("LINEAR_API_KEY")
if not key:
    st.error("Set LINEAR_API_KEY in your environment, then restart.\n\n"
             "`export LINEAR_API_KEY=lin_api_...`  (Linear → Settings → Security & access → API keys)")
    st.stop()

try:
    teams = load_teams(key)
except Exception as e:
    st.error(f"Couldn't reach Linear: {e}")
    st.stop()

team = st.sidebar.selectbox("Team", teams, format_func=lambda t: t["name"])
weeks = st.sidebar.slider("Window (weeks)", 2, 26, 8)
wip_limit = st.sidebar.number_input("WIP limit", min_value=1, value=5)
if st.sidebar.button("Refresh"):
    st.cache_data.clear()

completed, active = load(key, team["id"], weeks)

cts = metrics.cycle_times_days(completed)
p50 = metrics.percentile(cts, 50)
p85 = metrics.percentile(cts, 85)
tput = metrics.throughput_per_week(len(completed), weeks)
aged = metrics.ages_days(active)
wip = len(active)

# Leading indicators — act on these now
c1, c2, c3, c4 = st.columns(4)
c1.metric("WIP (now)", wip, delta=f"{wip - wip_limit:+d} vs limit",
          delta_color="inverse")
c2.metric("Throughput", f"{tput:.1f} / wk", help=f"{len(completed)} done in {weeks}w")
c3.metric("Cycle time p50", f"{p50:.1f} d" if p50 is not None else "—")
c4.metric("Cycle time p85 (SLE)", f"{p85:.1f} d" if p85 is not None else "—",
          help="85% of work ships within this many days")

if wip > wip_limit:
    st.warning(f"WIP {wip} is over your limit of {wip_limit} — cycle time is about to get worse.")

st.divider()
st.subheader("🧠 Daily insights")
or_key = os.environ.get("OPENROUTER_API_KEY")
if not or_key:
    st.caption("Set `OPENROUTER_API_KEY` in your environment to enable AI insights.")
else:
    summary = (
        f"Date: {datetime.now(timezone.utc).date()}\n"
        f"Team: {team['name']} · window: {weeks} weeks\n"
        f"WIP: {wip} (limit {wip_limit})\n"
        f"Throughput: {tput:.1f}/wk ({len(completed)} completed in {weeks}w)\n"
        f"Cycle time: p50 {p50:.1f}d, p85 {p85:.1f}d\n"
        "In-flight cards (id | age days | status | assignee):\n"
        + "\n".join(f"  {a['identifier']} | {a['age_days']:.1f} | {a['state']['name']} | {who(a)}"
                    for a in aged)
    )
    try:
        st.markdown(ai_insights(or_key, OR_MODEL, summary, str(datetime.now(timezone.utc).date())))
        st.caption(f"Model: {OR_MODEL} · cached for the day · sidebar Refresh regenerates.")
    except Exception as e:
        st.warning(f"Insights unavailable: {e}")

st.divider()
left, right = st.columns(2)

with left:
    st.subheader("Work item age — in flight")
    st.caption(f"Leading indicator. 🔴 past p85 SLE ({p85:.0f}d) · 🟡 past p50 "
               f"({p50:.0f}d) · 🟢 on track." if p50 is not None
               else "Leading indicator.")
    if aged:
        def health(age):
            if p85 is not None and age > p85:
                return "🔴"
            if p50 is not None and age > p50:
                return "🟡"
            return "🟢"
        df = pd.DataFrame(
            [{"": health(a["age_days"]),
              "id": a["identifier"],
              "age": round(a["age_days"], 1),
              "over SLE": round(a["age_days"] - p85, 1) if p85 is not None and a["age_days"] > p85 else None,
              "who": who(a),
              "status": a["state"]["name"],
              "what": a["title"][:45]}
             for a in aged]
        )
        st.dataframe(df, width="stretch", hide_index=True,
                     column_config={"age": st.column_config.NumberColumn("age", format="%.1f d"),
                                    "over SLE": st.column_config.NumberColumn("over SLE", format="+%.1f d")})
    else:
        st.write("Nothing in progress.")

with right:
    st.subheader("Cycle time distribution")
    if cts:
        slowest = max(cts)
        st.caption(f"n={len(cts)} · p50 {p50:.1f}d · p85 {p85:.1f}d · slowest {slowest:.0f}d "
                   "— report median + p85, never the mean.")
        bins = [0, 3, 7, 14, 30, float("inf")]
        labels = ["≤3d", "4–7d", "1–2wk", "2–4wk", ">4wk"]
        buckets = pd.cut(cts, bins=bins, labels=labels, right=True)
        counts = buckets.value_counts().reindex(labels).fillna(0).astype(int)
        st.bar_chart(counts, y_label="cards", x_label="cycle time")
    else:
        st.write("No completed cards with a start time in this window.")

st.divider()
st.subheader("Per person")
st.caption("Throughput/cycle are team-level signals; per-person is for load balance, "
           "not productivity ranking — high WIP per head is the thing to spot.")

rows = []
for name in sorted({who(i) for i in active} | {who(i) for i in completed}):
    a = [i for i in active if who(i) == name]
    c = [i for i in completed if who(i) == name]
    pcts = metrics.cycle_times_days(c)
    p50u = metrics.percentile(pcts, 50)
    p85u = metrics.percentile(pcts, 85)
    oldest = max((x["age_days"] for x in metrics.ages_days(a)), default=None)
    rows.append({
        "person": name,
        "WIP": len(a),
        f"done ({weeks}w)": len(c),
        "throughput/wk": round(metrics.throughput_per_week(len(c), weeks), 1),
        "cycle p50 (d)": round(p50u, 1) if p50u is not None else None,
        "cycle p85 (d)": round(p85u, 1) if p85u is not None else None,
        "oldest in-flight (d)": round(oldest, 1) if oldest is not None else None,
    })
st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
