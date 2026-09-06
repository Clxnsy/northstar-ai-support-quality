# Homelab Deployment

Northstar is designed to run on a workstation, mini PC, or local server.

## Local model path

Ollama is the simplest no-key setup:

```bash
ollama serve
ollama pull qwen3:8b
northstar serve --host 0.0.0.0 --port 8000
```

In the dashboard choose `Ollama`, set the model to `qwen3:8b`, and use `http://localhost:11434` when Northstar and Ollama run on the same host.

If Northstar is inside Docker and Ollama is on the host, use a host-reachable address. On Linux this may require adding a host gateway or using the host's LAN IP. Restrict Ollama exposure to trusted interfaces.

## OpenAI-compatible local servers

LM Studio, vLLM, LocalAI, and similar servers can be used through `openai_compatible`. Point Base URL to the server's `/v1` endpoint and provide a key only if that server requires one.

## Separate responder and judge

For better evaluation independence, run a smaller local model as the Support Agent and a stronger remote or local model as the judge. The CLI supports `--judge-model`; the API accepts a full `judge_provider` object.

## Backups

The only persistent service state is the SQLite database plus your procedure files. Back up:

- `data/northstar.db`
- `procedures/*.md`

WAL mode can create `northstar.db-wal` while the service is running. Stop the service or use SQLite's backup command for consistent snapshots.
