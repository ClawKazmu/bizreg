FROM python:3.11-slim

# Install system dependencies for Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libc6 \
    libgcc1 \
    libgomp1 \
    libstdc++6 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxcomposite1 \
    libxrandr2 \
    libxdamage1 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libcairo2 \
    libxkbcommon0 \
    libxshmfence1 \
    libxfixes3 \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libxi6 \
    libsm6 \
    libice6 \
    libglib2.0-0 \
    libnspr4 \
    libx11-xcb1 \
    libxcb1 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && playwright install chromium
COPY . .

ENV PORT=8000
CMD ["gunicorn", "app.main:app", "--bind", "0.0.0.0:$PORT", "-k", "uvicorn.workers.UvicornWorker"]
