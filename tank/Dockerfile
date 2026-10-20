FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py skala.py skill_costs.py admin.py graduate.py gold.py training.py schema.sql ./
COPY skills ./skills
RUN useradd -m tank && chown -R tank /app
# Baked at image build. Coolify passes SOURCE_COMMIT. A local build can pass GIT_SHA.
ARG SOURCE_COMMIT=
ARG GIT_SHA=
ENV TANK_GIT_SHA=${GIT_SHA:-$SOURCE_COMMIT}
USER tank
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
