FROM python:3.12-slim

# Pinned scanners. The downloads run at image build. A scan does not use the network.
# Gitleaks 8.28.0 checksums are from the upstream checksums file for that tag.
# Semgrep and pip-audit live in their own venvs so they cannot change the chassis packages.
# pip-audit and npm audit call a live service, so the scan reads the OSV files in
# /opt/osv instead of executing those clients.
ARG GITLEAKS_VERSION=8.28.0
ARG GITLEAKS_SHA_X64=a65b5253807a68ac0cafa4414031fd740aeb55f54fb7e55f386acb52e6a840eb
ARG GITLEAKS_SHA_ARM64=eff65261156100e5d94a6b3dec313d532fddfe19ae1590bf7a2b4f2699128356
ARG SEMGREP_VERSION=1.181.0
ARG PIP_AUDIT_VERSION=2.10.1
ARG TARGETARCH

WORKDIR /app
COPY _chassis/requirements.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git tar \
    && pip install --no-cache-dir -r requirements.txt \
    && python -m venv /opt/semgrep \
    && /opt/semgrep/bin/pip install --no-cache-dir "semgrep==${SEMGREP_VERSION}" \
    && python -m venv /opt/audit \
    && /opt/audit/bin/pip install --no-cache-dir "pip-audit==${PIP_AUDIT_VERSION}" \
    && arch="${TARGETARCH:-amd64}" \
    && case "$arch" in \
         amd64) gl_arch=x64; gl_sha="${GITLEAKS_SHA_X64}" ;; \
         arm64) gl_arch=arm64; gl_sha="${GITLEAKS_SHA_ARM64}" ;; \
         *) echo "unsupported arch: $arch" >&2; exit 1 ;; \
       esac \
    && curl -fsSL -o /tmp/gitleaks.tar.gz "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_${gl_arch}.tar.gz" \
    && echo "${gl_sha}  /tmp/gitleaks.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/gitleaks.tar.gz -C /usr/local/bin gitleaks \
    && chmod 755 /usr/local/bin/gitleaks \
    && rm -rf /tmp/gitleaks.tar.gz /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 agent \
    && mkdir -p /data /opt/osv \
    && chown agent:agent /data /opt/osv
COPY _chassis/chassis /app/chassis
COPY radix/app.py /app/app.py
COPY radix/net.py /app/net.py
COPY radix/scanlib /app/scanlib
COPY radix/scanlib/osv/ /opt/osv/
RUN chown -R agent:agent /app /opt/osv
USER agent
ENV AGENT_NAME=radix \
    DATA_DIR=/data \
    PYTHONUNBUFFERED=1 \
    RADIX_USE_SYSTEM_TOOLS=1 \
    RADIX_OSV_DIR=/opt/osv \
    SEMGREP_BIN=/opt/semgrep/bin/semgrep \
    PIP_AUDIT_BIN=/opt/audit/bin/pip-audit \
    SEMGREP_SEND_METRICS=off \
    SEMGREP_ENABLE_VERSION_CHECK=0 \
    GIT_TERMINAL_PROMPT=0
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
