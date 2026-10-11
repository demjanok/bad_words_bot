# ── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install dependencies into an isolated prefix so the final image stays small
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim

# Non-root user for security
RUN addgroup --system botgroup && adduser --system --ingroup botgroup botuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy only the source files needed at runtime
COPY main.py logging_config.py ./

# These files are mounted at runtime via volumes (see docker-compose.yml),
# but we copy defaults so the image can run without a mounted volume.
COPY bad_words.txt config.yaml ./

# Run as non-root
USER botuser

# Stream logs directly to stdout/stderr (no buffering)
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
