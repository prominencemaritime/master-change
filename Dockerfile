# Use Python 3.13 to match your local version
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Accept build arguments for user ID and group ID
ARG UID
ARG GID

# Install system dependencies and create user
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/* \
    && (getent group $GID || addgroup --gid $GID appuser) \
    && adduser --disabled-password --gecos "" --uid $UID --gid $GID appuser

# Set timezone
ENV TZ=Europe/Athens
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy project structure
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY queries/ ./queries/
COPY media/ ./media/
COPY tests/ ./tests/

# Create necessary directories and set ownership
RUN mkdir -p logs data && chown -R $UID:$GID /app

# Make healthcheck script executable
RUN chmod +x /app/scripts/healthcheck.py

# Set Python to run in unbuffered mode (see logs in real-time)
ENV PYTHONUNBUFFERED=1

# Switch to non-root user
USER appuser

# Run with scheduling enabled by default using new main.py entry point
CMD ["python", "-m", "src.main"]

# For daily scheduled tasks (SCHEDULE_TIMES=12:00,18:00)
HEALTHCHECK --interval=5m --timeout=10s --start-period=2m --retries=2 \
  CMD python3 /app/scripts/healthcheck.py

# For frequent tasks (SCHEDULE_FREQUENCY_HOURS=1)
#HEALTHCHECK --interval=2m --timeout=10s --start-period=2m --retries=2 \
#  CMD python3 /app/scripts/healthcheck.py

# For very frequent tasks (SCHEDULE_FREQUENCY_HOURS=0.25)
#HEALTHCHECK --interval=1m --timeout=10s --start-period=1m --retries=3 \
#  CMD python3 /app/scripts/healthcheck.py
