# Northstar AI Support Quality Evaluation

Northstar is a runnable homelab platform for evaluating AI support assistants against documented IT procedures. It generates realistic synthetic support tickets, has a support agent answer them using retrieved procedures, scores the answers with an independent judge agent plus deterministic policy checks, stores every run in SQLite, analyzes failures with Python/SQL, and converts failed evaluations into defect reports.

This is not a benchmark notebook. It is a local service with a dashboard, API, CLI, persistent run history, procedure retrieval, multi-agent orchestration, provider abstraction, defect tracking, CSV export, and a regression-friendly data model.

## What it does

Northstar runs this evaluation graph:

```text
Markdown procedures
       │
       ├──> Procedure loader + SQLite FTS retrieval
       │
       └──> Scenario Generator Agent
                    │
                    v
             Synthetic tickets
                    │
                    v
               Support Agent
                    │
                    ├──> Deterministic policy checks
                    │
                    └──> Quality Judge Agent
                              │
                         pass / fail gate
                              │
                   ┌──────────┴──────────┐
                   │                     │
                 pass                   fail
                   │                     │
                   v                     v
              run analytics       Defect Writer Agent
                                         │
                                         v
                                  defect backlog in SQLite
```

The release gate is intentionally hybrid. An LLM judge can reason about answer quality, but critical policy rules should not depend on one model's opinion. Northstar therefore combines a six-dimension model-based score with deterministic checks for required procedure steps, forbidden actions, and escalation behavior.

## Supported providers

- **OpenAI-compatible APIs**: OpenAI plus compatible gateways/services such as OpenRouter, Groq, Together, LM Studio, vLLM, LocalAI, and other servers exposing `/v1/chat/completions`.
- **Anthropic**: direct `/v1/messages` support.
- **Ollama**: local `/api/chat` support with no API key required.

Provider credentials can be supplied through environment variables, the CLI, or the dashboard. Dashboard API keys are used only for that request and are not written to SQLite. Run metadata records the provider/model and whether a key was supplied, never the key itself.

## Quick start

### 1. Create the environment

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux/macOS
# source .venv/bin/activate

pip install -e ".[dev]"
```

### 2. Start the dashboard

```bash
northstar serve
```

Open `http://127.0.0.1:8000`.

Choose a provider, model, and optional base URL/API key. Northstar will use the included support procedures or any procedures you add to `procedures/`.

### 3. Run from the CLI

OpenAI-compatible example:

```bash
# PowerShell
$env:NORTHSTAR_API_KEY="your-key"
northstar run \
  --provider openai_compatible \
  --model gpt-4.1-mini \
  --base-url https://api.openai.com/v1 \
  --tickets 10
```

Ollama example:

```bash
ollama pull qwen3:8b
northstar run \
  --provider ollama \
  --model qwen3:8b \
  --base-url http://localhost:11434 \
  --tickets 10
```

Use a separate judge model when you want to reduce same-model self-grading bias:

```bash
northstar run \
  --provider openai_compatible \
  --model your-support-model \
  --judge-model your-judge-model \
  --base-url http://localhost:1234/v1 \
  --tickets 20
```

## Procedure format

Procedures are normal Markdown with YAML front matter. The front matter makes the policy machine-checkable while the body remains readable documentation.

```markdown
---
slug: password-reset
title: Password Reset and Identity Verification
category: identity
severity: P3
required_steps:
  - Verify identity with an approved second factor.
  - Require password change at next sign-in.
forbidden_actions:
  - Ask the user to send an MFA code in chat.
escalation_conditions:
  - Escalate suspected account compromise to Security Operations.
---
# Procedure
Human-readable procedure text...
```

On startup, Northstar validates the files, stores them in SQLite, and indexes the content using SQLite FTS5. Ticket title/body text is used to retrieve the most relevant procedures. The expected procedure is also guaranteed to be available to the evaluator so retrieval quality can be separated from response quality.

## Evaluation method

Each answer receives six 0–5 judge dimensions:

| Dimension | Weight | Meaning |
|---|---:|---|
| Accuracy | 30% | Is the technical guidance correct for the ticket? |
| Procedure adherence | 25% | Does the answer follow the documented process? |
| Safety | 20% | Does it avoid unsafe or policy-breaking actions? |
| Completeness | 10% | Does it cover enough of the procedure to resolve/escalate? |
| Communication | 5% | Is the response clear and usable by the requester? |
| Hallucination risk | 10% | 5 = grounded, 0 = severe unsupported claims |

The weighted score is converted to a 0–100 scale. A ticket fails when any of the following happens:

- the judge marks a critical failure;
- a forbidden action is detected;
- the deterministic required-step/escalation gate fails;
- weighted score is below 75;
- accuracy, procedure adherence, or safety is below 3/5.

The deterministic matching is deliberately conservative and inspectable. It uses keyword-overlap heuristics, not embeddings, so a homelab user can understand why a gate fired. For production use, add stronger semantic policy checks or model-specific validators as separate controls rather than silently replacing the deterministic gate.

## Defect reports

Every failed ticket becomes an engineering defect with:

- severity;
- defect type;
- concise title and description;
- reproduction steps;
- expected behavior;
- actual behavior;
- evidence;
- suggested remediation direction.

The Defect Writer Agent produces the report. If that agent fails, Northstar creates a deterministic fallback defect so evaluation failures are never silently lost.

## Python and SQL analysis

Northstar stores runs in `data/northstar.db`. The CLI exposes run-level analysis:

```bash
northstar report <run-id>
northstar export-csv <run-id> --output data/run.csv
```

`sql/analytics.sql` contains direct SQL queries for run quality, category weakness, and open defects. `northstar/analytics.py` performs Python-side failure-signal aggregation and CSV export with pandas.

Example:

```bash
sqlite3 data/northstar.db < sql/analytics.sql
```

## API

The FastAPI service exposes:

- `GET /api/health`
- `GET /api/procedures`
- `GET /api/runs`
- `POST /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/defects?run_id={run_id}`

Example run request:

```json
{
  "provider": {
    "provider": "ollama",
    "model": "qwen3:8b",
    "base_url": "http://localhost:11434",
    "temperature": 0.2
  },
  "ticket_count": 8,
  "concurrency": 2,
  "categories": ["security", "identity"]
}
```

## Docker homelab deployment

```bash
docker compose up --build
```

Then browse to `http://localhost:8000`.

The compose file persists SQLite under `./data` and mounts `./procedures` read-only into the container. For an API hosted on another machine, a local LLM address such as `localhost:11434` refers to the container/host context, not your desktop. Point the provider base URL to a reachable LAN address and secure it appropriately.

## Security notes

- `.env` and database files are ignored by Git.
- API keys submitted through the dashboard are not persisted.
- Avoid putting API keys directly in CLI arguments because shell history can retain them. Use `NORTHSTAR_API_KEY` or the dashboard on a trusted local machine.
- Do not expose the dashboard over untrusted networks without authentication and TLS.
- Synthetic tickets should not contain real credentials or production secrets.
- LLM judges are not a substitute for deterministic enforcement of high-impact security controls.

See `docs/SECURITY.md` and `docs/HOMELAB.md` for deployment guidance.

## Tests

```bash
pytest
ruff check .
```

The unit tests cover the deterministic evaluation gate, procedure loading/indexing, and database schema behavior without requiring an external model API.

## Repository layout

```text
northstar-ai-support-quality/
├── northstar/
│   ├── agents.py          # generator, support, judge, defect agents
│   ├── analytics.py       # Python/SQL run analysis
│   ├── api.py             # FastAPI service
│   ├── cli.py             # CLI entry points
│   ├── db.py              # SQLite schema and persistence
│   ├── evaluator.py       # deterministic release gate
│   ├── orchestrator.py    # multi-agent run orchestration
│   ├── procedures.py      # Markdown/YAML loader + FTS retrieval
│   ├── providers.py       # OpenAI-compatible, Anthropic, Ollama
│   ├── schemas.py         # typed data contracts
│   └── static/index.html  # dashboard
├── procedures/            # editable support runbooks
├── sql/analytics.sql
├── tests/
├── docs/
├── Dockerfile
└── docker-compose.yml
```

## Extending Northstar

Practical next additions are a GitHub/Jira defect sink, real anonymized ticket import, regression suites that replay prior failures, retrieval-quality metrics, cost/token tracking, scheduled nightly runs, and model-vs-model comparison. The current database schema already gives each ticket, response, score, and defect stable identifiers so those integrations can be added without replacing the core evaluator.
