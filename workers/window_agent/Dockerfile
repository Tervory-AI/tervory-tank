# Reuse the existing worker computer, tools and non-root account.
FROM tervory-worker-task:1
USER root
RUN apt-get update && apt-get install -y --no-install-recommends bubblewrap && rm -rf /var/lib/apt/lists/*
COPY cli /opt/tervory/cli
RUN cd /opt/tervory/cli && npm ci --omit=dev --ignore-scripts
COPY workers/window_agent /opt/tervory/workers/window_agent
USER 1001:1001
ENTRYPOINT ["python3", "-m", "workers.window_agent.task"]
