# Multi-stage build for llama.cpp server
FROM ubuntu:22.04 AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    && rm -rf /var/lib/apt/lists/*

# Clone and build llama.cpp (CPU version)
RUN git clone https://github.com/ggerganov/llama.cpp.git && \
    cd llama.cpp && \
    cmake -B build && \
    cmake --build build --config Release -j$(nproc)

# Runtime stage
FROM ubuntu:22.04

WORKDIR /app

# Copy built binary
COPY --from=builder /build/llama.cpp/build/bin/llama-server /usr/local/bin/

EXPOSE 8080

ENTRYPOINT ["llama-server"]
