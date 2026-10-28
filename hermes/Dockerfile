FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv \
    FASTEMBED_CACHE_PATH=/opt/fastembed \
    HERMES_EMBED_MODEL=BAAI/bge-small-en-v1.5
COPY requirements.txt model.json ./
# Pillow 11.3.0 has advisories fixed only in 13.0.0, but every fastembed release caps
# pillow<13 (0.6.1 caps <12). Hermes only does text embeddings; Pillow 13 was checked
# locally with a real bge-small embed. Laid over with --no-deps (PR grok/d-advisory-pins).
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --no-deps pillow==13.0.0 \
    && python -c "import json; from huggingface_hub import snapshot_download; m=json.load(open('model.json')); snapshot_download(repo_id=m['repository'], revision=m['revision'], local_dir=m['directory'], allow_patterns=['*.json', 'model_optimized.onnx'])" \
    && useradd --create-home --uid 1000 hermes \
    && mkdir -p /srv/hermes \
    && chown -R hermes:hermes /opt/fastembed /srv
# specific_model_path bypasses fastembed's Hub metadata/cache lookup. No runtime
# download, even on a missing/corrupt model: rebuilding the image is the repair.
ENV HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
COPY model.json /srv/hermes/model.json
COPY *.py /srv/hermes/
USER hermes
EXPOSE 8000
CMD ["uvicorn", "hermes.main:app", "--host", "0.0.0.0", "--port", "8000"]
