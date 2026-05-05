# Security

## Reporting Security Issues

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them to the Microsoft Security Response Center (MSRC) at
[https://msrc.microsoft.com/create-report](https://aka.ms/report-security-issue).

If you prefer to submit without logging in, send email to
[secure@microsoft.com](mailto:secure@microsoft.com). If possible, encrypt your
message with our PGP key; please download it from the
[Microsoft Security Response Center PGP Key page](https://aka.ms/security-pgp-key).

You should receive a response within 24 hours. If for some reason you do not,
please follow up via email to ensure we received your original message.

Please include the requested information listed below (as much as you can
provide) to help us better understand the nature and scope of the possible issue:

- Type of issue (e.g., buffer overflow, SQL injection, cross-site scripting, etc.)
- Full paths of source file(s) related to the manifestation of the issue
- The location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit the issue

This information will help us triage your report more quickly.

## Preferred Languages

We prefer all communications to be in English.

## Policy

Microsoft follows the principle of
[Coordinated Vulnerability Disclosure](https://aka.ms/security-cvd).

## Security Considerations for TompoMCP

TompoMCP accesses Power BI / Microsoft Fabric APIs using your Azure identity.
It does **not** store credentials, tokens, or sensitive data persistently. All
API interactions use short-lived tokens from `DefaultAzureCredential`.

### Sensitivity Label Handling

TompoMCP may temporarily downgrade a semantic model's sensitivity label (from
Confidential → General) to read its definition metadata. The label is restored
immediately after extraction. This operation:

- Only occurs when `getDefinition` fails with a 403 due to sensitivity labels
- Requires the user to have Owner/Admin permissions on the artifact
- Is logged for auditability
- Restores the original label in a `finally` block to ensure restoration even on failure

If you have concerns about this behavior for your organization, you can restrict
access to workspaces with confidential labels.
