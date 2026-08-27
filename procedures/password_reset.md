---
slug: password-reset
title: Password Reset and Identity Verification
category: identity
severity: P3
required_steps:
  - Verify the user's identity with an approved second factor before resetting credentials.
  - Confirm the affected corporate username or email address.
  - Reset the password through the approved identity management workflow.
  - Require a password change at next sign-in and remind the user not to reuse prior passwords.
  - Revoke active sessions if compromise is suspected.
forbidden_actions:
  - Reset a password based only on caller ID, email display name, or knowledge of personal details.
  - Ask the user to send an existing password, MFA code, or recovery code in chat.
escalation_conditions:
  - Escalate to the security team when the user reports an unexpected MFA prompt or suspected account compromise.
---
# Procedure

1. Identify the account by corporate username or company email. Do not treat a display name as proof of identity.
2. Complete an approved identity-verification method. Examples include an enrolled authentication factor, verified service-desk callback workflow, or manager-assisted recovery process defined by the organization.
3. Never ask the user to disclose their current password, one-time passcode, backup code, or authenticator seed.
4. Perform the password reset through the identity-management console or approved self-service recovery flow.
5. Require the user to choose a new password at next sign-in and advise them not to reuse a prior password.
6. If the user reports an unexpected MFA prompt, impossible travel, unknown session, or other compromise indicator, revoke sessions if authorized and escalate to Security Operations.
