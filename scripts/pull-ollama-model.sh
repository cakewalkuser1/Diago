#!/bin/bash
# Pull the DiagBot chat model into the Ollama container.
# Run after: docker-compose up -d ollama
# Usage: ./scripts/pull-ollama-model.sh [model]
MODEL=${1:-llama3.1}
CONTAINER=${OLLAMA_CONTAINER:-diago-ollama}

echo "Waiting for Ollama to be ready..."
for i in {1..30}; do
  if docker exec "$CONTAINER" ollama list >/dev/null 2>&1; then
    echo "Ollama is ready."
    break
  fi
  sleep 2
done

echo "Pulling model: $MODEL (this may take a few minutes)..."
docker exec "$CONTAINER" ollama pull "$MODEL"
echo "Done. DiagBot chat will use $MODEL."
