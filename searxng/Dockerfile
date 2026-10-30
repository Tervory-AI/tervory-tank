# SearXNG: Tervory's own search engine. Internal only (never exposed); Base and Market Lab query it.
# Config is baked in because Coolify ignores bind mounts.
FROM searxng/searxng:2026.10.25-54ca1d9cf
COPY --chown=searxng:searxng settings.yml /etc/searxng/settings.yml
USER searxng
