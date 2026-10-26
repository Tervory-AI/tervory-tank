FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv \
    FASTEMBED_CACHE_PATH=/opt/fastembed \
    HERMES_EMBED_MODEL=BAAI/bge-small-en-v1.5
COPY requirements.lock requirements-pillow.lock ./
# Pillow 11.3.0 has advisories fixed only in 13.0.0, but every fastembed release caps
# pillow<13 (0.6.1 caps <12). Hermes only does text embeddings; Pillow 13 was checked
# locally with a real bge-small embed. Laid over with --no-deps (PR grok/d-advisory-pins).
RUN --mount=type=secret,id=system_ca \
    if [ -s /run/secrets/system_ca ]; then \
      export PIP_CERT=/run/secrets/system_ca SSL_CERT_FILE=/run/secrets/system_ca \
        REQUESTS_CA_BUNDLE=/run/secrets/system_ca CURL_CA_BUNDLE=/run/secrets/system_ca \
        NODE_EXTRA_CA_CERTS=/run/secrets/system_ca GIT_SSL_CAINFO=/run/secrets/system_ca; \
    fi; \
    pip install --require-hashes --no-cache-dir -r requirements.lock \
    && pip install --require-hashes --no-cache-dir --no-deps -r requirements-pillow.lock \
    && python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5')" \
    && useradd --create-home --uid 1000 hermes \
    && mkdir -p /srv/hermes \
    && chown -R hermes:hermes /opt/fastembed /srv
# The model is on disk in /opt/fastembed. HF_HUB_OFFLINE is not set: fastembed
# 0.6 checks the model's file list online before using the cache, and in offline
# mode that check fails and Hermes never starts (seen in production, 13 Oct).
# Only model metadata goes out; client text never leaves this container.
COPY *.py /srv/hermes/
USER hermes
EXPOSE 8000
CMD ["uvicorn", "hermes.main:app", "--host", "0.0.0.0", "--port", "8000"]
