FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt constraints-langgraph.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py skala.py skill_costs.py admin.py graduate.py gold.py training.py controls.py dashboards.py research.py bench.py proof.py savings_defaults.py savings_export.py savings_indexes.py agent_skills.py rig_brain_routes.py rig_forge_routes.py rig_three_d.py market_lab_routes.py cl100k_base.tiktoken cl100k_base.LICENSE storage.py ghost_routes.py command.py workers_status.py access.py rig_feed_mapping.py vault.py moa.py schema.sql base_public_http.py base_product.py base_queries.py base_repository.py base_reference_status.py base_metrics.py base_evidence.py vendor_meter.py ./
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
