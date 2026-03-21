# Stage 1: Builder — install dependencies with poetry
FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.2.1

# Copy dependency files first (maximizes Docker layer cache)
COPY pyproject.toml poetry.lock ./

# Install production dependencies into a virtual env
RUN poetry config virtualenvs.in-project true && \
    poetry install --only main --no-root --no-interaction --no-ansi

# Stage 2: Runtime — lean production image
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy virtual env from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app"

# Copy source code
COPY src/ ./src/

# Copy Streamlit theme configuration
COPY .streamlit/ ./.streamlit/

# Streamlit server config for containerized environment
RUN printf '[server]\nheadless = true\nport = 8501\naddress = "0.0.0.0"\nenableCORS = false\nenableXsrfProtection = true\n\n[browser]\ngatherUsageStats = false\n' \
    > /app/.streamlit/server.toml

# Run as non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

ENTRYPOINT ["streamlit", "run", "src/ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
