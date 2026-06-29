FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# deps first for layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app.py metrics.py ./

EXPOSE 8501
# keys (LINEAR_API_KEY, OPENROUTER_API_KEY) are injected at runtime, not baked in
CMD ["uv", "run", "--no-sync", "streamlit", "run", "app.py", \
     "--server.address", "0.0.0.0", "--server.port", "8501", "--server.headless", "true"]
