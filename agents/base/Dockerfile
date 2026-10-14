FROM python:3.12-slim
WORKDIR /app
COPY _chassis/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 1000 agent \
    && mkdir -p /data \
    && chown agent:agent /data
COPY _chassis/chassis /app/chassis
COPY base/app.py /app/app.py
COPY base/pipeline.py /app/pipeline.py
COPY base/room.py /app/room.py
USER agent
ENV AGENT_NAME=base \
    DATA_DIR=/data \
    PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
