FROM python:3.12-slim
WORKDIR /app
COPY _chassis/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 1000 agent \
    && mkdir -p /data \
    && chown agent:agent /data
COPY _chassis/chassis /app/chassis
COPY rig/rigbox /app/rigbox
COPY rig/rig_brain /app/rig_brain
COPY rig/app.py /app/app.py
COPY rig/gold_sources.py /app/gold_sources.py
COPY rig/schema.sql /app/schema.sql
COPY rig/english-20k.txt /app/english-20k.txt
COPY rig/shopping.txt /app/shopping.txt
COPY rig/catalogues /app/catalogues
USER agent
ENV AGENT_NAME=rig \
    DATA_DIR=/data \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
