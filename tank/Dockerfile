# syntax=docker/dockerfile:1
FROM python:3.12-slim
WORKDIR /app
COPY tank/requirements.txt tank/constraints-langgraph.txt ./
COPY tank/requirements-routellm.txt tank/requirements-routellm-wheel.txt tank/routellm_build.py tank/semantic_encoder.py ./
# Heavy dependencies and both CPU models install BEFORE the code is copied,
# so an ordinary code change reuses this cached layer instead of reinstalling ~2 GB.
# Optional trust bundle for managed cloud builds; never retained in a layer.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements.txt -r requirements-routellm.txt && \
    pip install --no-cache-dir --no-deps --require-hashes -r requirements-routellm-wheel.txt && \
    python routellm_build.py /opt/routellm && \
    python semantic_encoder.py
# Every Tank module is copied by pattern, so a PR that adds a module never edits this line
# (it used to be a hand-kept list that clashed on almost every Tank PR).
COPY tank/*.py tank/schema.sql tank/cl100k_base.tiktoken tank/cl100k_base.LICENSE ./
COPY tank/fonts ./fonts
COPY tank/skills ./skills
COPY jobs/train/run.py jobs/train/train.py ./jobs/train/
RUN useradd -m tank && chown -R tank /app
# Baked at image build. Coolify passes SOURCE_COMMIT. A local build can pass GIT_SHA.
ARG SOURCE_COMMIT=
ARG GIT_SHA=
ENV LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false
ENV TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
ENV TANK_GIT_SHA=${GIT_SHA:-$SOURCE_COMMIT}
USER tank
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
