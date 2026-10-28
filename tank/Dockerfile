# syntax=docker/dockerfile:1
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt constraints-langgraph.txt ./
COPY requirements-routellm.txt requirements-routellm-wheel.txt routellm_build.py ./
# Heavy dependencies and the RouteLLM CPU weights install BEFORE the code is copied,
# so an ordinary code change reuses this cached layer instead of reinstalling ~2 GB.
# Optional trust bundle for managed cloud builds; never retained in a layer.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements.txt -r requirements-routellm.txt && \
    pip install --no-cache-dir --no-deps --require-hashes -r requirements-routellm-wheel.txt && \
    python routellm_build.py /opt/routellm
COPY routellm_shadow.py ./
COPY main.py batch_providers.py skala.py skill_costs.py admin.py graduate.py gold.py training.py controls.py dashboards.py research.py bench.py proof.py savings_defaults.py savings_export.py savings_indexes.py agent_skills.py rig_brain_routes.py rig_forge_routes.py rig_three_d.py market_lab_routes.py cl100k_base.tiktoken cl100k_base.LICENSE storage.py ghost_routes.py command.py command_repo.py workers_status.py access.py rig_feed_mapping.py vault.py moa.py schema.sql base_public_http.py base_product.py base_queries.py base_repository.py base_reference_status.py base_metrics.py base_evidence.py vendor_meter.py ./
COPY fonts ./fonts
COPY skills ./skills
RUN useradd -m tank && chown -R tank /app
# Baked at image build. Coolify passes SOURCE_COMMIT. A local build can pass GIT_SHA.
ARG SOURCE_COMMIT=
ARG GIT_SHA=
ENV LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
ENV TANK_GIT_SHA=${GIT_SHA:-$SOURCE_COMMIT}
USER tank
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
