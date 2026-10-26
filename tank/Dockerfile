FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
WORKDIR /app
COPY requirements.txt constraints-langgraph.txt ./
COPY requirements.lock ./
RUN --mount=type=secret,id=system_ca \
    if [ -s /run/secrets/system_ca ]; then \
      export PIP_CERT=/run/secrets/system_ca SSL_CERT_FILE=/run/secrets/system_ca \
        REQUESTS_CA_BUNDLE=/run/secrets/system_ca CURL_CA_BUNDLE=/run/secrets/system_ca \
        NODE_EXTRA_CA_CERTS=/run/secrets/system_ca GIT_SSL_CAINFO=/run/secrets/system_ca; \
    fi; \
    pip install --require-hashes --no-cache-dir -r requirements.lock -c constraints-langgraph.txt
COPY main.py skala.py skill_costs.py admin.py graduate.py gold.py training.py controls.py dashboards.py research.py bench.py proof.py savings_defaults.py savings_export.py savings_indexes.py agent_skills.py rig_brain_routes.py rig_forge_routes.py rig_three_d.py cl100k_base.tiktoken cl100k_base.LICENSE storage.py ghost_routes.py command.py workers_status.py access.py rig_feed_mapping.py vault.py moa.py schema.sql ./
COPY fonts ./fonts
COPY skills ./skills
RUN useradd -m tank && chown -R tank /app
# Baked at image build. Coolify passes SOURCE_COMMIT. A local build can pass GIT_SHA.
ARG SOURCE_COMMIT=
ARG GIT_SHA=
ENV LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false
ENV TANK_GIT_SHA=${GIT_SHA:-$SOURCE_COMMIT}
USER tank
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
