FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @mariozechner/pi-coding-agent@0.73.1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /root/.pi/agent     && cp /app/docker/pi-models.json /root/.pi/agent/models.json

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
