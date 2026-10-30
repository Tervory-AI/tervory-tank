FROM python:3.12-slim
COPY tank/requirements.txt tank/constraints-langgraph.txt /deps/
RUN --mount=type=secret,id=proxy_ca PIP_CERT=/run/secrets/proxy_ca pip install --no-cache-dir -r /deps/requirements.txt aiosmtpd==1.4.6
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false
