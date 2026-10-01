FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LIBREOFFICE_BIN=/usr/bin/soffice \
    MALLOC_ARENA_MAX=2

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-writer \
        fontconfig \
        fonts-liberation \
        fonts-crosextra-carlito \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/uploads/reports

CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]
