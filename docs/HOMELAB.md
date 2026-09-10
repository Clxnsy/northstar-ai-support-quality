# Homelab Deployment

Northstar is designed to run on a workstation, mini PC, or local server.

## Local model path

Ollama is the simplest no-key setup:

```bash
ollama serve
ollama pull qwen3:8b
northstar serve --port 8000
```

In the dashboard choose `Ollama`, set the model to `qwen3:8b`, and use `http://localhost:11434` when Northstar and Ollama run on the same host.

Compose binds the dashboard to `127.0.0.1:8000` and includes a host-gateway mapping. If Ollama runs on the host, use `http://host.docker.internal:11434`; the model server must listen on an interface reachable from Docker. If it only listens on host loopback, adjust the model server's bind address and restrict access with your firewall, or run Northstar directly on the host. Inside a container, `localhost` refers to that container.

## OpenAI-compatible local servers

LM Studio, vLLM, LocalAI, and similar servers can be used through `openai_compatible`. Point Base URL to the server's `/v1` endpoint and provide a key only if that server requires one.

## Separate responder and judge

For better evaluation independence, run a smaller local model as the Support Agent and a stronger remote or local model as the judge. The CLI supports `--judge-model`, `--judge-provider`, `--judge-base-url`, and `--judge-api-key-env`. The dashboard supports the same configuration; the API accepts a full `judge_provider` object.

## Backups

The only persistent service state is the SQLite database plus your procedure files. Back up:

- `data/northstar.db`
- `procedures/*.md`

WAL mode can create `northstar.db-wal` while the service is running. Stop the service or use SQLite's backup command for consistent snapshots.

## Service operations

Run `docker compose up --build --wait` to build and wait for a healthy service. Use `docker compose logs northstar` for startup diagnostics. Set `NORTHSTAR_API_KEY` in the host environment or a gitignored `.env` file for Compose, or use the ephemeral dashboard field. `./data` persists across container recreation and `./procedures` is mounted read-only. Restart after changing procedure files, or run `northstar sync-procedures` on a native installation.

Use one Northstar worker per database. For LAN access, deliberately change the port binding and put authentication and TLS in front of the service. The API can contact user-supplied model endpoints and has no built-in authentication, so do not expose it directly to the internet.
