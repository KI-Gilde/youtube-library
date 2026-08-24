#!/bin/bash

echo "YouTube Library - Setup & Start"
echo "================================"

# Check for .env file
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

# Create data directories
mkdir -p data/videos data/audio data/transcripts data/transcripts_refined data/thumbnails models

# Download models if needed
echo ""
echo "Checking/downloading models..."

# Use python3/pip3 if python/pip not available
PYTHON_CMD=$(command -v python3 || command -v python)

if [ -z "$PYTHON_CMD" ]; then
    echo "ERROR: Python nicht gefunden. Bitte Python 3 installieren."
    exit 1
fi

# Create virtual environment if not exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv .venv
fi

# Activate venv and install dependencies
source .venv/bin/activate
pip install -q faster-whisper 2>/dev/null || {
    echo "Installing Python dependencies for model download..."
    pip install faster-whisper
}
python download_models.py
deactivate

# Build and start
echo "Starte Docker Compose..."
docker compose up --build -d

echo ""
echo "Services werden gestartet..."
echo ""
echo "  Frontend:    http://localhost:9070"
echo "  Backend API: http://localhost:9071"
echo "  API Docs:    http://localhost:9071/docs"
echo "  Qdrant UI:   http://localhost:9073/dashboard"
echo ""
echo "Port-Range: 9070-9080 (9076-9080 frei fuer weitere Container)"
echo ""
echo "Logs anzeigen: docker compose logs -f"
echo "Stoppen:       docker compose down"
