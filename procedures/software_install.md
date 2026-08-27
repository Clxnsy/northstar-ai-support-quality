---
slug: software-install
title: Managed Software Installation Request
category: endpoint
severity: P4
required_steps:
  - Confirm the software name, business purpose, device, and requesting user.
  - Check the approved software catalog and licensing requirements.
  - Use the managed deployment platform when the package is available.
  - Route unapproved or privileged software through the documented approval process.
  - Record the installed version and outcome in the ticket.
forbidden_actions:
  - Give local administrator credentials to the end user.
  - Download business software from an unofficial mirror or file-sharing site.
escalation_conditions:
  - Escalate when the application is not approved, requires a new license, or requests kernel, driver, or security-control changes.
---
# Procedure

Collect the requested product, version if relevant, device, user, and business need. Search the approved software catalog first. Use the endpoint-management platform for an available managed package. Software outside the catalog, paid licensing, drivers, kernel components, browser root certificates, or changes to security controls require the defined approval path. Record the final package version and whether installation succeeded.
