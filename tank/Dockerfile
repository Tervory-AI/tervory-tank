FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py skala.py admin.py schema.sql ./
COPY skills ./skills
RUN useradd -m tank && chown -R tank /app
USER tank
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
