# Privacy Notice — `fabric-cli-deploy`

_Last updated: 2025-01_

This plugin orchestrates a Microsoft Fabric workspace deployment from a local repository. It is designed so that **no data leaves the operator's machine except via the official `fab` CLI to Microsoft Fabric APIs** — and even that traffic is scoped to whatever the operator has already authenticated for via `fab auth login`.

This document is a plain-English companion to `skills/SKILL.md §14`.

---

## 1. What the plugin processes

| Data | Source | Stored where | Retention |
|---|---|---|---|
| Workspace name, tenant short-name, environment | Operator (via chat or config) | `Config/fabric_config.json` on operator's disk | Until operator deletes |
| Spark pool size, autoscale settings, OneLake folder list | Operator (config) | Same as above | Same |
| User UPNs for RBAC (`accessControl.user`) | Operator (config) | Same | Same |
| Storage account names, connection IDs, shortcut targets | Operator (config) | Same | Same |
| Operator's own UPN | `fab auth status` checkpoint output | Chat transcript only (one line in pre-flight) | Host policy |
| Per-artifact deploy status (success / skip / fail) | `oneinstaller.py` parsing Fabric API responses | `Logs/deployment_log_DDMMYYYY.csv` on operator's disk | Until operator deletes |
| Verbose execution trace | `oneinstaller.py` stdout | `Logs/runninglog_DDMMYYYY.txt` on operator's disk | Until operator deletes |

## 2. What the plugin does **NOT** collect or transmit

- ❌ No telemetry to Microsoft, Anthropic, GitHub, the plugin author, or any third party.
- ❌ No usage counters, no anonymous identifiers, no error-reporting beacons.
- ❌ No phone-home check for updates.
- ❌ No analytics pixels, no callback URLs.
- ❌ No PII beyond what the operator explicitly puts in `fabric_config.json` (and even that stays on disk).
- ❌ No transmission of notebook content, pipeline definitions, or model files to anywhere except the Fabric workspace the operator is deploying to (via `fab import`).

## 3. Outbound network connections

During a deployment, **exactly two** processes initiate network calls:

1. **`fab` CLI** → Microsoft Fabric REST APIs (`*.fabric.microsoft.com`, `*.azure.com`, `*.microsoft.com`).
   These calls are authorized by the operator's prior `fab auth login` and use Microsoft Entra ID tokens cached by `fab` (the plugin never sees the tokens).
2. **`python`** running `oneinstaller.py` → no outbound calls of its own. It only invokes `fab`.

The skill (agent layer) makes **zero** direct network calls.

## 4. Secrets

- The plugin **never** writes secrets to disk on its own.
- If `Config/fabric_config.json` contains a secret (e.g., `clientSecret`), it remains on disk under the operator's control. The plugin only **reads** it to pass to `fab`.
- When the plugin needs to display a config snippet in chat (e.g., during diff confirmation), it applies regex-based redaction per `SKILL.md §7.4`. Examples of redacted values: AAD client secrets, storage account keys, JWT/bearer tokens, connection strings containing `AccountKey=` or `Password=`, GitHub PATs, SAS tokens.
- Recommended: store secrets in Azure Key Vault and use `${KEYVAULT_NAME}` style references in config (the underlying `oneinstaller.py` supports this pattern).

## 5. Host-controlled chat transcripts

This plugin runs inside a chat host (Claude / Copilot CLI). The chat transcript itself is controlled by the host application and is governed by **the host's** privacy policy — not by this plugin. The plugin does not export, archive, or duplicate transcripts.

## 6. Your control

- **To delete all plugin output:** delete the `Logs/` folder under your FabricCLI repo.
- **To inspect what was deployed:** open `Logs/deployment_log_DDMMYYYY.csv` (one row per artifact).
- **To uninstall:** remove the plugin via `/plugin` in your agency session, or delete the plugin folder. No system-wide state is left behind.

## 7. Reporting a privacy concern

See `SECURITY.md` for the reporting workflow. Privacy issues are treated as security issues.
