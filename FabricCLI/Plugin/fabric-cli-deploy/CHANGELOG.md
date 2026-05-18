# Changelog

All notable changes to `fabric-cli-deploy` follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `LICENSE` (MIT) at plugin root.
- `evals/` directory with ten fixture files (`E-01.yaml` … `E-10.yaml`) and a `README.md` describing the harness contract for the §15 evaluation anchors.
- Sibling reference docs `skills/THREAT_MODEL.md` and `skills/PRIVACY_NOTES.md` carrying the full §13 / §14 content extracted from `SKILL.md`.
- Conversation E in `examples/multi-turn-refinement.md` demonstrating recovery from a partial-failure deployment.
- Marketplace metadata in `.claude-plugin/plugin.json`: `license`, `keywords`, `repository`, `homepage`, `engines`.

### Changed
- `SKILL.md` §13 and §14 trimmed to one-paragraph summaries that point to the new sibling files; the canonical tables now live in `THREAT_MODEL.md` / `PRIVACY_NOTES.md`.
- `SKILL.md` §2.1: row for `validate_config` clarified — the operation enforces required-keys-per-verb (§4.1); `schemas/fabric_config.schema.json` ships for documentation / editor IntelliSense and is not invoked via `jsonschema.validate`.
- `SKILL.md` trigger-phrase line: cosmetic fix (space after the slash-command, consistent quoting).
- `README.md`: marketplace structure link annotated as Microsoft-internal (raw URL retained, not rendered as a clickable link).

### Verified
- `fab auth status` confirmed present in `ms-fabric-cli` v1.6.1 (see [`commands/auth`](https://microsoft.github.io/fabric-cli/commands/auth/)); no change required to F-03.

## [1.0.0] — Initial release

### Added
- 7 verbs: `plan`, `full`, `infra-only`, `code-only`, `update-config`, `validate`, `status`.
- 21 domain operations (`ask_user`, `read_config`, `write_config`, `validate_config`, `check_python_runtime`, `check_fabric_cli`, `check_fabric_auth`, `inventory_artifacts`, `check_placeholder_hygiene`, `deploy_lakehouse`, `deploy_connection`, `deploy_shortcut`, `deploy_spark_pool`, `deploy_onelake_folder`, `assign_workspace_access`, `deploy_notebook`, `deploy_pipeline`, `deploy_semantic_model`, `deploy_report`, `read_audit_log`, `emit_summary`) layered over 5 runtime primitives.
- 15 enumerated failure scenarios (F-01 → F-15) with detect / report / remediate / retry-limit / stop conditions.
- 6-phase deployment lifecycle: intake → preflight → config → inventory → execute → summary.
- Verbatim final-summary format.
- Multi-pattern secret redaction (AAD client secret, storage account key, JWT, connection string, SAS token, GitHub PAT).
- Input sanitization regex/enum per field (workspace name, tenant, environment, paths, URLs, GUIDs, node sizes).
- Filesystem scoping confined to FabricCLI repo root.
- Prompt-injection resistance (read content treated as data; adversarial markers flagged via F-13).
- Production deployment gate (`--confirm-prod` + workspace-name retype).
- Threat model with 10 in-scope threats (T-01 → T-10) and explicit out-of-scope statements.
- Privacy notice (`PRIVACY.md`) and security policy (`SECURITY.md`).
- 10 evaluation anchors (E-01 → E-10) for marketplace eval harness.
- JSON Schema for `fabric_config.json` validation.
- Worked example (Contoso Retail) with entity decomposition, dependency graph, file tree, sample CSV, verbatim summary, idempotent re-run summary, partial-failure summary.
- Multi-turn refinement examples and realistic prompt examples.

### Compatibility
- `ms-fabric-cli` ≥ 1.2.0
- Python ≥ 3.10
- FabricCLI Deployment Kit `oneinstaller.py` ≥ 1.0
