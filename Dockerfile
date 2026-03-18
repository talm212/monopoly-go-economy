# Stage 1: Builder — export dependencies from poetry
FROM python:3.12-slim AS builder

WORKDIR /app

# Install poetry
RUN pip install --no-cache-dir poetry==2.2.1

# Copy only dependency files first (maximizes Docker layer cache)
COPY pyproject.toml poetry.lock ./

# Export production dependencies to requirements.txt
# Avoids needing poetry in the runtime image
RUN poetry export -f requirements.txt --without dev --without infra -o requirements.txt

# Stage 2: Runtime — lean production image
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install only production dependencies
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Copy Streamlit theme configuration
COPY .streamlit/ ./.streamlit/

# Streamlit server configuration for containerized environment
RUN mkdir -p /app/.streamlit && \
    printf '[server]\nheadless = true\nport = 8501\naddress = "0.0.0.0"\nenableCORS = false\n\n[browser]\ngatherUsageStats = false\n' \
    > /app/.streamlit/server.toml

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

ENTRYPOINT ["streamlit", "run", "src/ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
