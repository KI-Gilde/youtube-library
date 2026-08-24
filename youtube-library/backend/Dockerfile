FROM python:3.11-slim

WORKDIR /app

# System dependencies for yt-dlp, ffmpeg, whisper, and embeddings
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    build-essential \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create data directories
RUN mkdir -p /data/videos /data/audio /data/transcripts /data/transcripts_refined

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
