# Trendyol Scraper API — Coolify / Docker
FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY api.py scraper.py config.py models.py ./

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

# Coolify genelde PORT verir; yoksa 8000
CMD ["sh", "-c", "exec uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
