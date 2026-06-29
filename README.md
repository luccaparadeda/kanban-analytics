# kanban-analytics

[![CI](https://github.com/luccaparadeda/kanban-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/luccaparadeda/kanban-analytics/actions/workflows/ci.yml)

Streamlit dashboard of **Kanban flow metrics** for a [Linear](https://linear.app)
team — throughput, cycle time (p50/p85), WIP, and work item age, plus optional
AI-generated daily insights. All metrics are computed from `startedAt` /
`completedAt` / `state.type` via Linear's GraphQL API.

Grounded in **Little's Law** (`cycle time ≈ WIP ÷ throughput`):

- **Leading** (act now): WIP, work item age.
- **Lagging** (report/forecast): throughput, cycle time.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env   # then fill in your keys
uv run --env-file .env streamlit run app.py
```

Or export the vars yourself and run `uv run streamlit run app.py`.

## Configuration

| Variable | Required | Purpose |
|---|---|---|
| `LINEAR_API_KEY` | yes | Linear → Settings → Security & access → API keys |
| `OPENROUTER_API_KEY` | no | Enables the AI daily-insights panel ([openrouter.ai](https://openrouter.ai)) |
| `OPENROUTER_MODEL` | no | Model slug, default `anthropic/claude-sonnet-4.5` |

In the sidebar: pick the **team**, the **window** (weeks of history for the
lagging metrics), and your **WIP limit** (the target current WIP is compared
against).

## Deploy with Docker

Every push to `main` builds and publishes an image to GHCR via CI. On your server:

```bash
docker run -d --name kanban-analytics -p 8501:8501 \
  -e LINEAR_API_KEY=lin_api_... \
  -e OPENROUTER_API_KEY=sk-or-... \
  ghcr.io/luccaparadeda/kanban-analytics:latest
```

Or with your `.env`: `docker run -d -p 8501:8501 --env-file .env ghcr.io/luccaparadeda/kanban-analytics:latest`

## Layout

| File | What |
|---|---|
| `app.py` | Linear fetch + Streamlit UI + OpenRouter insights |
| `metrics.py` | Pure flow-metric calculations, no I/O |
| `test_metrics.py` | Asserts for the metric math (`uv run python test_metrics.py`) |

## Contributing

PRs welcome. Keep `metrics.py` pure (no I/O) and add an assert to
`test_metrics.py` for any new calculation. CI runs the tests on every PR.

## License

[MIT](LICENSE)
