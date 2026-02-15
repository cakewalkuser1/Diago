# Hosting Diago with Ollama

Run Diago's backend and Ollama together so DiagBot chat works without users installing anything.

## Quick Start (Docker Compose)

```bash
# 1. Start Ollama and the API
docker-compose up -d

# 2. Pull the chat model (one-time, ~2GB for llama3.1)
./scripts/pull-ollama-model.sh        # Linux/macOS
# or
.\scripts\pull-ollama-model.ps1       # Windows PowerShell
```

The API runs at `http://localhost:8000`. Set your frontend's API base URL to point here.

## Architecture

```
User App (frontend)  →  Diago API (:8000)  →  Ollama (:11434)
```

- **Ollama**: Serves the LLM. Models are stored in the `ollama_data` volume.
- **Diago API**: Proxies chat requests to Ollama. Connects via `OLLAMA_URL=http://ollama:11434`.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://ollama:11434` | Ollama service URL (Docker network) |
| `OLLAMA_MODEL` | `llama3.1` | Model used for DiagBot chat |
| `OLLAMA_AUTO_START` | `false` | Do not auto-start Ollama (it runs in Docker) |

## GPU Support

For NVIDIA GPU, add to the `ollama` service in `docker-compose.yml`:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

Then run: `docker-compose up -d`

## Other Models

To use a different model (e.g. `llama3.2`, `mistral`):

1. Pull it: `docker exec diago-ollama ollama pull llama3.2`
2. Set `OLLAMA_MODEL=llama3.2` in the `api` service environment.
