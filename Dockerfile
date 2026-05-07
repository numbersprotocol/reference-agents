FROM python:3.11-slim

LABEL org.opencontainers.image.title="Numbers Protocol Reference Agents"
LABEL org.opencontainers.image.source="https://github.com/numbersprotocol/reference-agents"
LABEL org.opencontainers.image.licenses="MIT"

# Create non-root user for runtime
RUN useradd -r -s /bin/false -m -d /home/agent agent

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent source
COPY common.py .
COPY provart.py .
COPY newsprove.py .
COPY agentlog.py .
COPY dataprove.py .
COPY socialprove.py .
COPY researchprove.py .
COPY codeprove.py .

# State directory (mounted as volume in docker-compose)
RUN mkdir -p /app/state && chown agent:agent /app/state

# Tmp directory for agent file writes
RUN mkdir -p /tmp && chown agent:agent /tmp

USER agent
ENV PYTHONUNBUFFERED=1
ENV STATE_DIR=/app/state

# Default: override CMD in docker-compose per service
CMD ["python", "-u", "provart.py"]
