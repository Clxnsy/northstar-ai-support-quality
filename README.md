# Northstar Support Copilot

A working IT support workspace where a **human analyst** stays in charge. You paste in a ticket, Northstar pulls the relevant procedures, suggests troubleshooting steps, drafts a customer reply, and flags when to escalate. Then you do what analysts actually do: verify the facts, edit the reply, record what happened. Northstar proposes. You decide.

**It never sends replies, resets accounts, runs commands, or touches devices.** That is a design choice, not a missing feature.

## What it does
- Ingests a support ticket and searches **seven built-in runbooks** (full-text search) for the matching procedure
- Drafts procedure-backed troubleshooting steps, clarifying questions, escalation guidance, and a customer reply
- Persists cases, original drafts, procedure snapshots, and your review history in **SQLite** across restarts
- Works with **OpenAI, Anthropic, OpenRouter, and local Ollama** models, plus any OpenAI-compatible server, with model discovery so you are not stuck on a stale model list
- Optional **quality lab**: score AI responses against policy checks, file defect reports, and run SQL/Python analytics on the results
- Ships with **40 automated tests**, a Docker Compose setup, and a CLI

## How to run it
Python 3.11 or newer. From the repo directory:

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

Or with Docker Compose:

```bash
docker compose up
```

Copy `.env.example` to `.env` and add your API keys (BYOK). Ollama runs fully local with no key at all.

## Daily workflow
1. Pick your provider: OpenAI, OpenRouter, Anthropic, Ollama, or a custom endpoint.
2. Click **Load available models** and choose a current text model (or paste a model ID).
3. Paste a ticket and select the procedures that apply.
4. Review the suggested steps, questions, escalation guidance, and reply draft against the procedure references.
5. Edit the reply, add your notes, mark steps complete.
6. Save your review, then copy the reply into your own support system yourself.

## Repo layout
- `northstar/`: the application (FastAPI service, retrieval, review workflow)
- `procedures/`: the seven support runbooks the copilot searches
- `sql/`: schema and analytics queries for the quality lab
- `tests/`: 40 automated tests
- `scripts/`: CLI and utilities
- `docs/`: workflow documentation
- `data/`: SQLite case history (created at runtime)
- `docker-compose.yml`, `Dockerfile`: containerized deployment

## What this project proves
I built the tool I wished I had on a service desk: procedure-grounded, review-first, and honest about what AI should not do unsupervised. It exercises the full loop I sell to employers: Python/FastAPI backend, SQLite persistence and full-text retrieval, Docker packaging, multi-provider LLM integration, and a QA mindset baked in through the quality lab and test suite.
