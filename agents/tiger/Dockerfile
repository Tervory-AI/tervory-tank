FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
WORKDIR /app
COPY _chassis/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 1000 agent \
    && mkdir -p /data \
    && chown agent:agent /data
COPY _chassis/chassis /app/chassis
COPY tiger/app.py /app/app.py
COPY tiger/watch.py /app/watch.py
COPY tiger/change_alert.py /app/change_alert.py
COPY tiger/page_guard.py /app/page_guard.py
COPY tiger/feedback.py /app/feedback.py
COPY tiger/gold_sources.py /app/gold_sources.py
COPY tiger/gold /app/gold
USER agent
ENV AGENT_NAME=tiger \
    DATA_DIR=/data \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
