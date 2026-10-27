# LiteLLM with Tank's model rosters baked in (no bind mount needed under Coolify).
# config.yaml is the US roster; config.za.yaml is the South Africa roster.
# Pinned to an exact release. LiteLLM retired the rolling main-latest tag in 2026
# (https://docs.litellm.ai/blog/cleaner-release-versions). Upgrade by changing this
# version on purpose in its own PR, never by a moving tag.
# v1.106.3 (2026-10-24): same-minor pin for GHOST-2 haste rebuild (Node security
# release path + image-signing key rotation upstream). Verify node -v after deploy.
FROM ghcr.io/berriai/litellm:v1.106.3
COPY config.yaml /app/config.yaml
COPY config.za.yaml /app/config.za.yaml
