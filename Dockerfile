FROM python:3.11-slim

LABEL org.opencontainers.image.title="Numbers Protocol Reference Agents"
LABEL org.opencontainers.image.source="https://github.com/numbersprotocol/reference-agents"
LABEL org.opencontainers.image.licenses="MIT"

RUN useradd -r -s /bin/false -m -d /home/agent agent

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY common.py .
COPY newsprove.py .
COPY socialprove.py .

RUN mkdir -p /app/state /tmp && chown -R agent:agent /app/state /tmp

USER agent
ENV PYTHONUNBUFFERED=1
ENV STATE_DIR=/app/state

# docker-compose overrides CMD per service.
CMD ["python", "-u", "newsprove.py"]
