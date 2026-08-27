---
slug: phishing-report
title: Suspected Phishing Message
category: security
severity: P2
required_steps:
  - Tell the user not to click additional links, open attachments, or reply to the suspected message.
  - Preserve the original message and report it using the approved phishing-report mechanism.
  - Determine whether the user clicked a link, opened an attachment, entered credentials, approved MFA, or executed a file.
  - Escalate confirmed interaction or credential exposure to Security Operations immediately.
  - If credentials were exposed, initiate the approved account containment process.
forbidden_actions:
  - Ask the user to forward a suspicious attachment to a personal email account.
  - Advise the user to investigate the malicious link by opening it in a browser.
escalation_conditions:
  - Escalate immediately when the user clicked, entered credentials, approved MFA, opened an attachment, or executed content.
---
# Procedure

Treat suspected phishing as a security event. Keep the original message intact, use the organization's report-phish control or approved security mailbox, and collect the minimum facts needed to determine exposure. If the user interacted with the content, escalate to Security Operations immediately. For credential exposure, follow the identity-compromise procedure: reset credentials through an approved workflow, revoke active sessions when authorized, and review MFA state. Do not ask the end user to investigate the malicious content themselves.
