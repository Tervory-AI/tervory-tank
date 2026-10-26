FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
WORKDIR /app
COPY _chassis/requirements.lock /tmp/chassis-requirements.lock
COPY market_lab/feeds/requirements.txt /tmp/feeds-requirements.txt
COPY market_lab/feeds/requirements.lock /tmp/feeds-requirements.lock
RUN --mount=type=secret,id=system_ca \
    if [ -s /run/secrets/system_ca ]; then \
      export PIP_CERT=/run/secrets/system_ca SSL_CERT_FILE=/run/secrets/system_ca \
        REQUESTS_CA_BUNDLE=/run/secrets/system_ca CURL_CA_BUNDLE=/run/secrets/system_ca \
        NODE_EXTRA_CA_CERTS=/run/secrets/system_ca GIT_SSL_CAINFO=/run/secrets/system_ca; \
    fi; \
    pip install --require-hashes --no-cache-dir -r /tmp/chassis-requirements.lock -r /tmp/feeds-requirements.lock -c /tmp/feeds-requirements.txt \
    && useradd --create-home --uid 1000 agent \
    && mkdir -p /data \
    && chown agent:agent /data
COPY _chassis/chassis /app/chassis
COPY market_lab/feeds /app/feeds
COPY market_lab/core /app/core
COPY market_lab/engines /app/engines
COPY market_lab/schema.sql /app/schema.sql
COPY market_lab/app.py /app/app.py
COPY market_lab/gold_sources.py /app/gold_sources.py
USER agent
ENV AGENT_NAME=market_lab \
    DATA_DIR=/data \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
