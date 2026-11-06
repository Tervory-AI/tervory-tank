FROM python:3.12.15-slim-bookworm@sha256:57d96f71de145a98e7ceca18ee4ade77bba4103a33a72dfaea026b23625c6bf0 AS download
WORKDIR /build
COPY install.py ./
RUN python install.py /opt/local-model

FROM python:3.12.15-slim-bookworm@sha256:57d96f71de145a98e7ceca18ee4ade77bba4103a33a72dfaea026b23625c6bf0
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1=12.2.0-14+deb12u1 libstdc++6=12.2.0-14+deb12u1 && rm -rf /var/lib/apt/lists/*
COPY --from=download /opt/local-model /opt/local-model
COPY LICENSE.model LICENSE.large /opt/local-model/
ENV LD_LIBRARY_PATH=/opt/local-model/llama-b12173
USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["/opt/local-model/llama-b12173/llama-server"]
CMD ["--model", "/opt/local-model/model.gguf", "--alias", "local", "--host", "0.0.0.0", "--port", "8080", "--threads", "8", "--threads-batch", "8", "--ctx-size", "4096", "--parallel", "1", "--n-gpu-layers", "0"]
