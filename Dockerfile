FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PORT=8000
CMD ["gunicorn", "app.main:app", "--bind", "0.0.0.0:$PORT", "-k", "uvicorn.workers.UvicornWorker"]
