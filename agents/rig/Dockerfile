FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
WORKDIR /app
COPY _chassis/requirements.lock .
RUN --mount=type=secret,id=system_ca \
    if [ -s /run/secrets/system_ca ]; then \
      export PIP_CERT=/run/secrets/system_ca SSL_CERT_FILE=/run/secrets/system_ca \
        REQUESTS_CA_BUNDLE=/run/secrets/system_ca CURL_CA_BUNDLE=/run/secrets/system_ca \
        NODE_EXTRA_CA_CERTS=/run/secrets/system_ca GIT_SSL_CAINFO=/run/secrets/system_ca; \
    fi; \
    pip install --require-hashes --no-cache-dir -r requirements.lock \
    && useradd --create-home --uid 1000 agent \
    && mkdir -p /data \
    && chown agent:agent /data
COPY _chassis/chassis /app/chassis
COPY rig/rigbox /app/rigbox
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
CMD ["uvicorn", "rigbox.three_d.asgi:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]
