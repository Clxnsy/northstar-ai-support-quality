# Security

Northstar is a homelab engineering tool, not an internet-facing SaaS product.

## API keys

Dashboard keys are accepted in a run request, converted to a Pydantic secret, and retained only in memory while provider calls execute. The persisted run configuration drops the key and stores only `api_key_supplied: true|false`.

Prefer environment variables for unattended or repeat use:

```bash
export NORTHSTAR_API_KEY='...'
```

Do not commit `.env`. It is ignored by Git.

## Network exposure

The default server binds to `127.0.0.1`. Binding to `0.0.0.0` makes the service reachable from other interfaces. If you do that, use a trusted LAN, a firewall, and preferably an authenticated TLS reverse proxy. The built-in dashboard has no user authentication.

## Data handling

Use synthetic or properly anonymized support tickets. Do not seed the evaluator with production passwords, MFA seeds, recovery codes, private keys, or sensitive customer data.

## Prompt injection

Ticket text is deliberately untrusted. Agent system prompts define role boundaries, and procedure context is explicitly labeled authoritative. For high-assurance testing, add input segmentation, tool allowlists, and provider-specific structured-output enforcement.
