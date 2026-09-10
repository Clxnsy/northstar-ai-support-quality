# Northstar Support Copilot

A practical IT support workspace that helps a **human analyst** investigate tickets, draft replies, and follow documented procedures. Northstar proposes work; the analyst verifies facts, edits the reply, and records what actually happened.

**It never sends replies, resets accounts, runs commands, or changes devices.** The quality lab is an optional place to test models and prompts with synthetic tickets.

## Daily support workflow

1. Choose OpenAI, OpenRouter, Anthropic, Ollama, or a custom OpenAI-compatible server.
2. Click **Load available models** and select a current text model, or enter its model ID.
3. Paste a ticket and optionally select relevant procedures.
4. Review the suggested steps, questions, escalation guidance, and reply draft.
5. Read the procedure references, edit the reply, and record your notes and completed steps.
6. Save your review, then copy the reviewed reply into your support system yourself.

Cases, original drafts, procedure snapshots, and human review history persist in SQLite across restarts. AI suggestions are never automatically marked as completed actions.

## Install and start

Python 3.11 or newer is required. Run from the repository directory:

```bash
git clone https://github.com/Clxnsy/northstar-ai-support-quality.git
cd northstar-ai-support-quality
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
northstar serve
```

Linux/macOS:

```bash
source .venv/bin/activate
python -m pip install -e ".[dev]"
northstar serve
```

Open **http://127.0.0.1:8000**. The [API documentation](http://127.0.0.1:8000/docs) is available once the server is running.

## Free public API demo

Click **Set up free demo** in the support workspace. This selects OpenRouter, the `openrouter/free` model, and a fictional sample ticket. Create your own free [OpenRouter API key](https://openrouter.ai/settings/keys), paste it into the key field, then prepare a draft.

The [Free Models Router](https://openrouter.ai/docs/guides/routing/routers/free-router) routes to available free models. Northstar does not configure a paid-model fallback. Availability and free-tier limits can change; a 429 means the provider is rate-limiting requests. The router can select different models across requests, so use a specific model for reproducible comparisons. Use fictional tickets for demos and review the selected provider's data policy before entering work information.

There is no shared API key in this repository. For a no-API-key setup, use a local Ollama model you have installed; select **Ollama** and load its model list.

## Current models and providers

| Provider | Default endpoint | Interface |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | Responses API; server-side response storage disabled |
| OpenRouter | `https://openrouter.ai/api/v1` | Chat Completions; current catalog and free router |
| Anthropic | `https://api.anthropic.com/v1` | Messages API |
| Ollama | `http://localhost:11434` | Local chat and installed-model list |
| Other compatible server | Your `/v1` URL | Chat Completions; LM Studio, vLLM, LocalAI, and similar servers |

No old model is hardcoded as the default. Model discovery asks the provider; manual model entry remains available when a server does not expose a catalog. Choose a text/chat model, not an embedding, image, or audio-only model.

Temperature is omitted by default to accommodate reasoning models. Advanced settings let you supply supported temperature/reasoning options or disable native JSON mode for compatible servers that reject it. The output must still match the validated JSON draft schema. See [OpenAI's current model guidance](https://developers.openai.com/api/docs/guides/latest-model) for model-specific restrictions.

Keys can come from the ephemeral dashboard field or `NORTHSTAR_API_KEY`. They are excluded from SQLite and exports. Provider error bodies are not saved. A hosted provider receives the ticket and retrieved procedures when you request a draft; use a local model if that data should remain on your machine.

## CLI

Write ticket details to a text file, then prepare a draft:

```bash
northstar assist --title "VPN portal unavailable" --ticket-file ticket.txt --provider openrouter --model openrouter/free
northstar case CASE_ID
northstar review CASE_ID --reply-file reviewed-reply.txt --notes "Verified internet connectivity"
```

`assist` uses `NORTHSTAR_API_KEY` by default. A review only records your decision locally; it never sends the reply.

The optional quality lab keeps the original evaluation commands:

```bash
northstar sync-procedures
northstar run --provider ollama --model YOUR_INSTALLED_MODEL --tickets 3
northstar report RUN_ID
northstar export-csv RUN_ID --output data/results.csv
```

For an independent quality judge, use `--judge-model`, `--judge-provider`, `--judge-base-url`, and `--judge-api-key-env`, or the lab's judge settings. See [Quality lab guide](docs/QUALITY_LAB.md) and [evaluation method](docs/EVALUATION_METHOD.md).

## Procedures and persistence

Edit the seven included Markdown runbooks in `procedures/`: password resets, account lockouts, VPN, phishing, malware, Microsoft 365 mail, and software installation. YAML front matter defines the slug, title, category, P1–P4 severity, required steps, forbidden actions, and escalation conditions. Startup validates them and indexes them with SQLite FTS5; no embedding service is needed.

Use `northstar sync-procedures` after edits, or restart. Slugs must be unique. The workspace's procedure library shows the actual authority used. Keyword-based review reminders can miss paraphrases or complex negation; they complement human judgment rather than certify an answer.

SQL tables include support cases and review history as well as runs, tickets, responses, scores, defects, and procedures. Back up `data/northstar.db` using SQLite's backup API or while the service is stopped, plus your procedure files. WAL and foreign keys are enabled.

## Docker and homelab

```bash
docker compose up --build --wait
```

Compose publishes **127.0.0.1:8000**, persists `./data`, mounts procedures read-only, and includes a health check. To reach Ollama on the host from Docker, try `http://host.docker.internal:11434`; the model server must listen on an interface reachable from the container.

Run **one application worker per database**. Drafts and evaluations run as in-process tasks. Interrupted work becomes failed on restart; completed results are retained and requests are not silently billed again. Start a new draft/run to retry.

The dashboard has no built-in authentication. For LAN access, use an authenticated TLS reverse proxy and appropriate firewall rules. See [Homelab deployment](docs/HOMELAB.md) and [security](docs/SECURITY.md).

## Verification

```bash
python scripts/check_repo.py
python -m ruff check .
```

The offline check compiles Python, validates and indexes procedures into a temporary SQLite database, exercises the installed CLI, starts an actual HTTP server, verifies health/procedure/dashboard routes, and runs tests. Tests cover provider request formats, model discovery, human reviews, restart persistence, secret handling, policy checks, fallback defects, and CSV export without an API key.

GitHub Actions runs on Windows/Linux with Python 3.11/3.12 and builds/starts the Docker service. Offline fixtures validate application behavior; a real model response still requires a reachable provider and its credentials when applicable.

## API highlights

- `GET /api/health`, `GET /api/procedures`, `GET /api/procedures/{slug}`
- `POST /api/models` — discover models using an ephemeral provider configuration
- `GET /api/cases`, `POST /api/cases`, `GET /api/cases/{id}`
- `POST /api/cases/{id}/review` — persist the analyst's edited reply and work record
- `GET /api/runs`, `POST /api/runs`, `GET /api/runs/{id}`
- `GET /api/runs/{id}/export.csv`, `GET /api/defects`

The support workspace is `/`; the optional quality lab is `/quality-lab`.
