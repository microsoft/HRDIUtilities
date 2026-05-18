# Privacy & Telemetry Posture — `fabric-cli-deploy`

This document is the full privacy posture referenced by [SKILL.md §14](./SKILL.md). It complements `PRIVACY.md` at the plugin root.

## 1. What stays local (always)

- `Config/fabric_config.json` — never leaves disk except via `fab` calls to Fabric APIs (which is the entire point).
- `Logs/runninglog_*.txt`, `Logs/deployment_log_*.csv` — written under the user's repo, never uploaded.
- Chat transcript — handled by the host (Claude / Copilot CLI), governed by the host's privacy policy. The skill itself does not duplicate transcript content anywhere.

## 2. What the skill never transmits

- No telemetry endpoint, no usage counters, no error-reporting beacon.
- No third-party services. The only outbound traffic from a deployment originates from `fab` → Fabric APIs.
- No GitHub callbacks, no analytics, no LLM training opt-in.

## 3. PII handling

- The skill does not solicit PII beyond what is operationally required: workspace name, tenant short-name, environment label, UPNs for RBAC.
- UPNs the operator provides for `accessControl.user` entries are written to `fabric_config.json` and passed to `fab role` — they are not logged in chat snippets unless the user explicitly asks to display the config.
- The `fab auth status` checkpoint may surface the operator's own UPN. This is shown only once during pre-flight and is the operator's own identity (no third-party data).

## 4. Data retention

- Local logs persist until the user deletes them. The skill does not auto-rotate or auto-delete.
- See `PRIVACY.md` at the plugin root for the full data-flow diagram.
