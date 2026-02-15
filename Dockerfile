# Diago API - runs alongside Ollama for DiagBot chat
FROM python:3.12-slim

WORKDIR /app

# Install system deps for audio (optional, for full diagnosis features)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements (Docker uses minimal set - no PyQt6, no llama-cpp)
COPY requirements-docker.txt requirements-docker.txt
RUN pip install --no-cache-dir -r requirements-docker.txt

COPY . .

# Default: run API on 8000
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
