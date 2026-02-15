# Pull the DiagBot chat model into the Ollama container.
# Run after: docker-compose up -d ollama
# Usage: .\scripts\pull-ollama-model.ps1 [model]
param([string]$Model = "llama3.1")
$Container = if ($env:OLLAMA_CONTAINER) { $env:OLLAMA_CONTAINER } else { "diago-ollama" }

Write-Host "Waiting for Ollama to be ready..."
for ($i = 1; $i -le 30; $i++) {
  docker exec $Container ollama list 2>$null
  if ($LASTEXITCODE -eq 0) {
    Write-Host "Ollama is ready."
    break
  }
  Start-Sleep -Seconds 2
}

Write-Host "Pulling model: $Model (this may take a few minutes)..."
docker exec $Container ollama pull $Model
Write-Host "Done. DiagBot chat will use $Model."
