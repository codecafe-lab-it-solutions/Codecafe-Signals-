# CodeCafe Signals dashboard for Hugging Face Spaces (Docker SDK) or any Docker host.
# Secrets (GROQ_API_KEY, GEMINI_API_KEY, DATABASE_URL, SECRET_KEY, ADMIN_*/DEMO_*) come from the host's
# secret settings at runtime; .env is never copied into the image (see .dockerignore).
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv

# Hugging Face runs containers as uid 1000
RUN useradd -m -u 1000 app
WORKDIR /app

COPY --chown=app pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project && chown -R app /app

COPY --chown=app . .
USER app

ENV HOST=0.0.0.0 PORT=7860 TRADING_MODE=paper PYTHONUNBUFFERED=1
EXPOSE 7860
CMD [".venv/bin/python", "dashboard_server.py"]
