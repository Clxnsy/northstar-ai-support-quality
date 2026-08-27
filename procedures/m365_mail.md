---
slug: m365-mail-delivery
title: Microsoft 365 Mail Delivery Troubleshooting
category: messaging
severity: P3
required_steps:
  - Determine whether the issue affects one sender, one recipient, a domain, or multiple users.
  - Collect the approximate send time, sender, recipient, subject, and any non-delivery report.
  - Check service health and message trace when authorized.
  - Distinguish spam or quarantine handling from transport failure.
  - Document the trace result or reason for escalation.
forbidden_actions:
  - Disable anti-spam or anti-phishing protection globally to deliver one message.
  - Whitelist an entire external domain without documented authorization.
escalation_conditions:
  - Escalate suspected tenant-wide mail flow incidents.
  - Escalate configuration changes that require messaging administrator privileges.
---
# Procedure

Scope the incident before changing anything. Obtain sender, recipient, approximate time, subject, and the exact non-delivery report if one exists. Check Microsoft 365 service health, then use message trace where authorized. A message in quarantine is different from a transport failure and should be handled according to the organization's security policy. Do not weaken tenant-wide filtering to solve a single delivery problem.
