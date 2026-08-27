---
slug: vpn-troubleshooting
title: Remote Access VPN Troubleshooting
category: network
severity: P3
required_steps:
  - Confirm general internet access before troubleshooting the VPN tunnel.
  - Record the VPN client error and connection timestamp.
  - Confirm system date and time are correct and the VPN client is supported and current.
  - Validate the user's account and MFA state without asking for an MFA code.
  - Test name resolution and access to an approved internal resource after the tunnel connects.
forbidden_actions:
  - Tell the user to disable endpoint protection or the host firewall as a permanent fix.
  - Ask the user to share an MFA one-time code.
escalation_conditions:
  - Escalate when multiple users are affected or the VPN gateway health check indicates an outage.
  - Escalate when certificate or device-compliance remediation requires administrator action.
---
# Procedure

Start by separating local internet problems from tunnel problems. Confirm the endpoint can reach normal internet sites, then capture the exact VPN error and time. Verify the clock, client version, account state, MFA enrollment, certificate validity where applicable, and device-compliance status. After connection, validate DNS and one approved internal resource. Do not permanently disable security controls. Multi-user impact should be treated as a service incident rather than individual endpoint troubleshooting.
