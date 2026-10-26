FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
WORKDIR /app
COPY requirements.lock .
RUN --mount=type=secret,id=system_ca \
    if [ -s /run/secrets/system_ca ]; then \
      export PIP_CERT=/run/secrets/system_ca SSL_CERT_FILE=/run/secrets/system_ca \
        REQUESTS_CA_BUNDLE=/run/secrets/system_ca CURL_CA_BUNDLE=/run/secrets/system_ca \
        NODE_EXTRA_CA_CERTS=/run/secrets/system_ca GIT_SSL_CAINFO=/run/secrets/system_ca; \
    fi; \
    pip install --require-hashes --no-cache-dir -r requirements.lock
COPY connector ./connector
RUN useradd -m mcp && chown -R mcp /app
USER mcp
EXPOSE 8000
# No access log: the sign-in redirect carries a one-time code in the query string.
CMD ["uvicorn", "connector.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
