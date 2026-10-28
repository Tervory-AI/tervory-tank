FROM python:3.12.10-slim-bookworm
WORKDIR /app
COPY requirements.txt .
# Optional build secret supplies the managed cloud's CA; normal builds use the
# image's system trust store. No credential is copied into the image.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then \
      cat /etc/ssl/certs/ca-certificates.crt /run/secrets/proxy_ca > /tmp/build-ca.pem; \
      PIP_CERT=/tmp/build-ca.pem pip install --no-cache-dir -r requirements.txt; \
      rm /tmp/build-ca.pem; \
    else pip install --no-cache-dir -r requirements.txt; fi
COPY . /app/researcher
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp
USER 65532:65532
EXPOSE 8000
CMD ["uvicorn", "researcher.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
