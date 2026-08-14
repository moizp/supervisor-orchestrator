FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY router_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

COPY router_service/main.py main.py

# Fetch the router GGUF from its private Hugging Face repo at build time,
# baked into the image — same reasoning as wellington-impact-lab's Dockerfile:
# Cloud Run scales to zero, baking in avoids re-downloading on every cold start.
ARG HF_TOKEN
RUN mkdir -p models && \
    curl -fL --retry 5 --retry-all-errors --retry-delay 5 \
    -H "Authorization: Bearer ${HF_TOKEN}" \
    -o models/router-q4km.gguf \
    https://huggingface.co/moiz-hf/supervisor-router-q4km/resolve/main/router-q4km.gguf

ENV PORT=8080
ENV MODEL_PATH=/app/models/router-q4km.gguf
EXPOSE 8080

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
