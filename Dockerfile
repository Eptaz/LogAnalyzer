FROM python:3.14-slim

WORKDIR /app

# Copy app code and requirements
COPY Main.py app.py requirements.txt entrypoint.sh ./
COPY templates ./templates

RUN apt-get update && apt-get install -y dos2unix && dos2unix entrypoint.sh && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir -r requirements.txt && chmod +x entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV DB_PATH=/data/anomalies.db
ENV NTFY_TOPIC=loganalyzer
ENV NTFY_URL=https://ntfy.sh

# Create directories for logs and database persistence
RUN mkdir -p /app/Logs /data

VOLUME ["/app/Logs", "/data"]
EXPOSE 5000

ENTRYPOINT ["/bin/sh", "./entrypoint.sh"]
