# Tiger: Tervory's browser. A real Chromium that loads a page the way a person's browser does,
# runs its JavaScript and waits for it to settle. Internal only; Tank's skills call it.
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 3000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "3000"]
