# Build with agents/ as context. This room composes the existing Rig host.
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY _chassis/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 1000 agent \
    && mkdir -p /data && chown agent:agent /data
COPY _chassis/chassis /app/chassis
COPY rig/rigbox /app/rigbox
COPY rig/app.py /app/app.py
COPY rig/gold_sources.py /app/gold_sources.py
COPY rig/schema.sql /app/schema.sql
COPY rig/english-20k.txt /app/english-20k.txt
COPY rig/shopping.txt /app/shopping.txt
COPY video_shop /app/video_shop
USER agent
# Rig owns shared catalogue/cart schema and existing Tank identity.
ENV AGENT_NAME=rig DATA_DIR=/data PYTHONUNBUFFERED=1 PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "video_shop.video_asgi:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]
