FROM python:3.12-slim
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
