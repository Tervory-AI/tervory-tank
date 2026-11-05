# The poller overrides scratch with the immutable ID of the worker image it just built.
# No external image is pulled here; reuse workers/task/Dockerfile and its tools.
FROM scratch
USER root
RUN apt-get update && apt-get install -y --no-install-recommends bubblewrap && rm -rf /var/lib/apt/lists/*
COPY cli /opt/tervory/cli
RUN cd /opt/tervory/cli && npm ci --omit=dev --ignore-scripts
COPY workers/window_agent /opt/tervory/workers/window_agent
USER 1001:1001
ENTRYPOINT ["python3", "-m", "workers.window_agent.task"]
