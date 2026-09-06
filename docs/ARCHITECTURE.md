# Architecture

Northstar separates support-policy authority, model execution, evaluation, and analytics so each can change independently.

## Components

### Procedure layer

Markdown files are human-readable source control artifacts. YAML front matter contains machine-checkable required steps, forbidden actions, and escalation conditions. At service startup, `northstar.procedures.sync_to_db()` validates and upserts each procedure into SQLite and SQLite FTS5.

### Provider layer

`northstar.providers` normalizes three provider families behind one async `complete_json()` contract:

- OpenAI-compatible `/chat/completions`
- Anthropic `/messages`
- Ollama `/api/chat`

Secrets live only in the provider object for the duration of a request and are excluded from persisted run configuration.

### Agent layer

Four agents have explicit responsibilities:

1. **Scenario Generator Agent** creates procedure-grounded synthetic incidents.
2. **Support Agent** is the system under evaluation.
3. **Quality Judge Agent** produces evidence-backed quality dimensions.
4. **Defect Writer Agent** converts failures into actionable defect reports.

The judge can use a separate model from the responder to reduce correlated grading bias.

### Evaluation layer

`northstar.evaluator` applies deterministic procedure checks independently of the judge model. This is the deployment gate. Model-based scoring adds nuance; deterministic checks make non-negotiable controls inspectable.

### Persistence and analytics

SQLite stores normalized run, ticket, response, score, and defect records. WAL mode allows the web service to read historical results while new evaluations write. SQL queries handle aggregation; pandas is used for CSV export and external analysis workflows.

## Data flow

1. Sync procedure documents.
2. Generate N synthetic tickets from the selected procedure set.
3. Retrieve top procedure candidates from ticket text.
4. Run Support Agent.
5. Run deterministic checks and independent Judge Agent.
6. Apply the release gate.
7. On failure, create a defect report.
8. Persist all artifacts.
9. Produce run/category/failure-signal analytics.

## Trust boundaries

The procedure repository is policy authority. Model output is untrusted data. Provider credentials are secrets. Synthetic tickets and model outputs can contain prompt-injection-like text; they are treated as test input, not instructions to the orchestration service.
