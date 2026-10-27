FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY connector ./connector
RUN useradd -m mcp && chown -R mcp /app
USER mcp
EXPOSE 8000
# No access log: the sign-in redirect carries a one-time code in the query string.
CMD ["uvicorn", "connector.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
