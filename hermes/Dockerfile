FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv \
    FASTEMBED_CACHE_PATH=/opt/fastembed \
    HERMES_EMBED_MODEL=BAAI/bge-small-en-v1.5
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5')" \
    && useradd --create-home --uid 1000 hermes \
    && mkdir -p /srv/hermes \
    && chown -R hermes:hermes /opt/fastembed /srv
# After the model is on disk, do not call out for weights at request time.
ENV HF_HUB_OFFLINE=1
COPY *.py /srv/hermes/
USER hermes
EXPOSE 8000
CMD ["uvicorn", "hermes.main:app", "--host", "0.0.0.0", "--port", "8000"]
