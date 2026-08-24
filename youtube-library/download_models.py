#!/usr/bin/env python3
"""Download all required models for YouTube Library.

Embeddings and LLM responses come from the configured OpenAI-compatible
API — only Whisper still runs locally.
"""


def download_whisper():
    """Download faster-whisper medium model."""
    from faster_whisper import WhisperModel
    print("Downloading Whisper model (medium)...")
    WhisperModel("medium", device="cpu", compute_type="int8")
    print("✓ Whisper model ready")


if __name__ == "__main__":
    print("\n=== Downloading Models ===\n")
    download_whisper()
    print("\n=== All models ready ===\n")
