---
slug: account-lockout
title: Repeated Account Lockout
category: identity
severity: P3
required_steps:
  - Verify the user's identity before unlocking or modifying the account.
  - Check the identity platform for lockout reason, timestamp, and recent failed authentication events.
  - Identify stale saved credentials on mapped drives, mobile mail clients, VPN clients, scheduled tasks, or services.
  - Unlock the account only after the source of repeated bad credentials is addressed or isolated.
forbidden_actions:
  - Repeatedly unlock the account without investigating the source of bad credentials.
  - Disable MFA to stop lockouts.
escalation_conditions:
  - Escalate to security when authentication events originate from unfamiliar locations or show password-spraying indicators.
---
# Procedure

Repeated lockouts usually indicate cached credentials or automated authentication attempts. Verify identity, inspect sign-in or domain-controller events, determine which device or service is sending bad credentials, and remove or update the stale credential. Common sources include old passwords in mobile mail, Windows Credential Manager, mapped drives, VPN profiles, services, and scheduled tasks. If the event pattern is suspicious, preserve the evidence and route the case to Security Operations.
