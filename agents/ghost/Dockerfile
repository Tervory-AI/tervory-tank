FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
WORKDIR /app
COPY _chassis/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 1000 agent \
    && mkdir -p /data && chown agent:agent /data
COPY ghost /app/ghost
USER agent
ENV AGENT_NAME=ghost DATA_DIR=/data PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "ghost.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
