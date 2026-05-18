# Security Policy — `fabric-cli-deploy`

_Last updated: 2025-01_

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x | ✅ |
| < 1.0 | ❌ (pre-release) |

## Reporting a vulnerability

If you discover a security issue in this plugin:

1. **Do not** open a public GitHub issue.
2. Email the plugin maintainer (see `author.email` in `.claude-plugin/plugin.json`) with subject prefix `[SECURITY]`.
3. Include: reproduction steps, affected version, expected vs. actual behavior, and the smallest possible PoC.
4. You will receive an acknowledgement within 2 business days. A coordinated fix and disclosure timeline will be agreed before any public discussion.

For vulnerabilities in **`ms-fabric-cli`** itself or in **Microsoft Fabric APIs**, follow [Microsoft Security Response Center](https://msrc.microsoft.com/) procedures instead.

---

## Security posture (summary)

Full threat model and mitigations are documented in `skills/SKILL.md §13`. The highlights:

### Hard guarantees
| Guarantee | Where enforced |
|---|---|
| No `shell=True`, no `Invoke-Expression`, no string-concatenated shell commands | `SKILL.md §7.9` |
| All user input regex-validated before any shell invocation | `SKILL.md §7.8` |
| Filesystem reads/writes confined to the FabricCLI repo root | `SKILL.md §7.2` |
| Multi-pattern secret redaction on every chat-bound message | `SKILL.md §7.4` |
| Read content treated as data, not instructions (prompt-injection resistance) | `SKILL.md §7.5` |
| Production deployments require explicit `--confirm-prod` + workspace-name retype | `SKILL.md §7.1` |
| Plugin makes zero direct network calls; only `fab` reaches the network | `SKILL.md §7.11` |
| Plugin handles no credentials directly; auth delegated to `fab auth login` | `SKILL.md §13.3` |
| Every `write_config` requires unified-diff + yes/no confirmation | `SKILL.md §7.3` |

### Dependencies
This plugin's runtime has **zero Python dependencies of its own**. It relies on:
- Python 3.10+ (operator-supplied)
- `ms-fabric-cli` 1.2.0+ (operator-supplied via `pip install ms-fabric-cli`)
- Python stdlib only inside `oneinstaller.py`

No `requirements.txt` for the plugin itself = no transitive CVE surface to monitor at the plugin layer. (The operator is responsible for keeping `ms-fabric-cli` patched.)

### Curated-marketplace promotion attestations

When this plugin is submitted for promotion from `playground` → curated marketplace, the following attestations apply:

- [x] **No hardcoded secrets.** Scanned with the Agent Governance Toolkit security scan.
- [x] **No critical/high CVEs in dependencies.** Plugin has zero direct deps; `ms-fabric-cli` is operator-managed.
- [x] **No dangerous code patterns.** No `eval`, no `exec`, no `shell=True`, no dynamic import from user input. (See `SKILL.md §7.9`.)
- [x] **Manifest valid.** `.claude-plugin/plugin.json` follows Claude plugin schema; SKILL.md has valid YAML frontmatter.
- [x] **Prompt-injection resistance.** Read content explicitly treated as data; adversarial markers detected and flagged (`SKILL.md §7.5`, F-13).
- [x] **Secret handling.** Plugin never persists, transmits, or echoes secrets; multi-pattern redaction on all chat output (`SKILL.md §7.4`).
- [x] **Filesystem scoping.** All I/O confined to FabricCLI repo root; symlinks, UNC, env-var interpolation rejected (`SKILL.md §7.2`, `§7.8`).
- [x] **Auth model.** Plugin handles no tokens, no passwords. Delegated to `fab`'s OS keychain integration (`SKILL.md §13.3`).
- [x] **Privacy.** No telemetry, no analytics, no third-party callbacks (`PRIVACY.md`).
- [x] **Audit trail.** Every action logged locally by `oneinstaller.py` (running log + structured CSV).
- [x] **Reversibility.** Idempotent + skip-if-exists ensures re-runs are safe. No destructive operations without explicit confirmation.

### Out-of-scope (operator's responsibility)
- Hardening the operator's local machine.
- Securing the `fab` token cache (OS keychain).
- Vetting notebook / pipeline content for runtime safety after deployment.
- Branch protection on the FabricCLI repo itself.
- Network egress controls (firewalls, proxies) for `fab` → Fabric API traffic.
