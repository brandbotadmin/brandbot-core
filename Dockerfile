FROM python:3.11-slim

WORKDIR /app

# Instalo paketat e sistemit
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Kopjo requirements dhe instalo libraritë
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopjo të gjithë kodin e projektit
COPY . .

# Eksporto portën
EXPOSE 10000

# Ekzekuto uvicorn duke i lidhur automatikisht variablën PORT të Render
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]