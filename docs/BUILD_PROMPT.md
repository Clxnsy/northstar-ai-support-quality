# Master build prompt

Build **Northstar AI Support Quality Evaluation** as a real, runnable homelab application, not a portfolio mockup, benchmark notebook, toy test harness, static website, or architecture-only exercise.

The finished project must let a user bring their own LLM API key or point to a local model server, load documented IT support procedures, generate realistic synthetic support tickets with an agent, have a support agent answer those tickets, evaluate the answers with an independent judge agent plus deterministic policy checks, persist complete run history in SQL, analyze failures with Python/SQL, and automatically convert failed evaluations into actionable defect reports.

## Product requirements

Create a local web application and CLI that can actually be used repeatedly. Use Python 3.11+ with FastAPI, SQLite, typed Pydantic models, async model calls, and a small no-build-step web dashboard. Include Docker support.

The application must support:

1. **Bring-your-own provider configuration**
   - OpenAI-compatible `/v1/chat/completions` endpoints.
   - Anthropic `/v1/messages`.
   - Ollama `/api/chat` for fully local use.
   - Configurable base URL and model name.
   - API keys supplied through environment variables, CLI-safe environment lookup, or a dashboard password field.
   - Never persist raw API keys in SQLite, logs, Git, or generated reports.

2. **Documented procedure knowledge base**
   - Store support procedures as Markdown with YAML front matter.
   - Front matter must include procedure slug, category, severity, required steps, forbidden actions, and conditional escalation rules.
   - Validate procedures on startup.
   - Index procedure text in SQLite FTS5 and retrieve relevant procedures for each ticket.
   - Include realistic starter procedures for password reset/identity verification, account lockout, VPN troubleshooting, phishing, endpoint malware, Microsoft 365 mail delivery, and managed software installation.

3. **Real multi-agent workflow**
   - Scenario Generator Agent: generates realistic synthetic enterprise support tickets grounded in the loaded procedures and includes difficult/adversarial details where appropriate.
   - Support Agent: answers the ticket using retrieved procedures and cannot claim actions it did not actually perform.
   - Quality Judge Agent: independently scores the answer against the authoritative procedure with evidence.
   - Defect Writer Agent: converts failures into reproducible engineering defects.
   - Allow the judge to use a different model/provider configuration from the support agent.

4. **Hybrid evaluation gate**
   - Judge dimensions: technical accuracy, procedure adherence, safety, completeness, communication quality, hallucination/grounding risk.
   - Weighted score on a 0–100 scale.
   - Deterministic checks for required procedure steps, forbidden actions, and escalation behavior.
   - Avoid obvious false positives such as flagging a response for saying “never send an MFA code.”
   - Conditional escalation rules must only trigger when the ticket actually matches the condition, except for procedures explicitly marked as always-escalate incidents.
   - A policy-breaking answer must fail even if the LLM judge gives it a high score.

5. **Persistent SQL run history**
   - SQLite tables for runs, tickets, responses, scores, defects, and procedures.
   - Stable IDs and foreign keys.
   - WAL mode and useful indexes.
   - Store provider/model metadata, latency, retrieved procedures, judge evidence, deterministic checks, verdicts, and defect status.
   - Do not store secrets.

6. **Python + SQL failure analysis**
   - Run-level pass rate, mean score, critical failures, and category breakdown.
   - Identify recurring failure signals such as missed required steps, unsafe actions, low safety, low accuracy, and low grounding scores.
   - Include a reusable SQL analytics file.
   - Include CSV export using pandas for external analysis.

7. **Defect reporting**
   - Every failed evaluation must produce a defect record.
   - Fields: severity, defect type, title, description, reproduction steps, expected behavior, actual behavior, evidence, suggested remediation, status.
   - If the Defect Writer Agent fails, create a deterministic fallback defect so failures are never silently dropped.

8. **Usable dashboard and API**
   - Dashboard fields for provider, model, base URL, API key, ticket count, concurrency, and optional categories.
   - Submit evaluation runs asynchronously and return a run ID immediately.
   - Poll/show run status, pass rate, mean score, failed count, critical failures, ticket-level score/verdict, and defect type.
   - Expose health, procedure, run, run-detail, and defect endpoints.

9. **CLI**
   - `northstar serve`
   - `northstar sync-procedures`
   - `northstar run`
   - `northstar report <run-id>`
   - `northstar export-csv <run-id>`
   - API key should be read from an environment variable rather than required directly on the command line.

10. **Homelab deployment**
    - Dockerfile and docker-compose file.
    - Persist SQLite data under `./data`.
    - Mount procedure files read-only in Docker.
    - Document local Ollama and OpenAI-compatible server use.
    - Document LAN/TLS/API-key security risks.

## Engineering quality requirements

Do not leave TODOs, empty modules, placeholder text, pseudocode, fake APIs, or “implement later” comments in required functionality. The repository must boot and the non-network test suite must run without any model API credentials.

Add unit tests for procedure loading/indexing, schema scoring, deterministic policy checks, forbidden-action negation, and conditional escalation behavior. Add an offline repository validation script. Run Python compilation, tests, procedure validation, SQLite initialization, package installation, CLI help, and API health/procedure smoke tests before considering the project complete.

Use clear separation of concerns: config, schemas, database, procedures/retrieval, providers, agents, evaluator, orchestration, analytics, API, CLI, dashboard.

## Repository and GitHub

Create a repository named `northstar-ai-support-quality`. If GitHub access is available and authenticated, create/push it under the **Clxnsy** account and set the remote to:

`https://github.com/Clxnsy/northstar-ai-support-quality.git`

Use multiple focused commits rather than one dump. Good commit boundaries include project scaffolding, procedure knowledge base, provider/agent layer, evaluator/orchestration, analytics/persistence, dashboard/API/CLI, and tests/documentation.

Do **not** fabricate or backdate Git author/committer timestamps to make the project appear older than it is. If authentic prior commits/files exist, preserve their original history. Otherwise create truthful commits while building. Do not claim a GitHub push succeeded unless the remote operation actually succeeds.

## Definition of done

The project is done only when:

- a user can clone it, install it, start the dashboard, supply a provider/model/API key or Ollama URL, and launch a real evaluation;
- generated tickets flow through the support agent, judge, deterministic policy gate, SQLite, analytics, and defect reporting;
- failures remain inspectable after restart;
- the dashboard and CLI both work;
- credentials are not persisted;
- tests pass without paid API access;
- documentation explains architecture, evaluation methodology, homelab deployment, and security;
- the Git repo contains the complete source with a clean `.gitignore` and focused commits;
- if remote GitHub access exists, the final code is actually pushed to `Clxnsy/northstar-ai-support-quality`.
