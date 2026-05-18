# Threat Model — `fabric-cli-deploy`

This document is the full threat model referenced by [SKILL.md §13](./SKILL.md). It is kept as a sibling file to keep the main behavioral contract focused.

The skill assumes a **trusted operator on an untrusted artifact set**. The operator has Fabric admin/contributor rights via prior `fab auth login`; the config and artifact files may have been authored by other contributors and SHOULD NOT be trusted to be benign.

## 1. In-scope threats (mitigated)

| # | Threat | Vector | Mitigation |
|---|---|---|---|
| T-01 | **Command injection** via crafted `workspaceName`, paths, or config values | User input or config file containing `;`, `` ` ``, `$()`, etc. | §7.8 reject-at-boundary regex; §7.9 argv-only invocation; no `shell=True`. |
| T-02 | **Path traversal** to read/write files outside the repo | `../../etc/passwd` in config, symlinks, UNC paths | §7.2 + §7.8 path normalization and repo-root containment check; reject symlinks. |
| T-03 | **Prompt injection** from notebook cells, pipeline JSON, READMEs the skill reads | Adversarial markdown / JSON comments / cell source | §7.5 treat-as-data; ignore embedded directives; F-13 detection + logging. |
| T-04 | **Secret exfiltration** via chat output (LLM echoing a value) | Reading config that contains a real secret; surfacing in error message or summary | §7.4 multi-pattern redaction applied to *every* chat-bound message; F-14. |
| T-05 | **Unauthorized prod deployment** triggered by ambiguous phrasing | "deploy it" interpreted as prod | §7.1 explicit `--confirm-prod` + workspace-name retype gate. |
| T-06 | **Supply-chain swap** of `oneinstaller.py` by an attacker who can write to the repo | Attacker modifies the orchestrator | Out of scope for the skill — relies on the repo's own integrity controls (git, branch protection). The skill does flag if the script is missing (F-04 family). |
| T-07 | **Stale/leaked credentials** in `fab` cache | Long-lived `fab auth login` session | Out of scope for the skill; surfaced by `fab auth status` in pre-flight (F-03 if stale). |
| T-08 | **Over-broad RBAC assignment** via mistyped UPN | `j.smith@cotnoso.com` (typo) granted admin | §7.8 GUID/UPN validation + Phase 3 diff confirmation before write; user reviews each role before `oneinstaller.py` applies it. |
| T-09 | **Data-loss on config overwrite** | Skill rewrites a hand-edited config | §7.3 unified-diff + yes/no confirmation before every `write_config`. |
| T-10 | **Denial-of-service** via huge config / log files | Adversarial 10 GB JSON | Size cap (§7.8 / §10) — refuse to parse > 5 MB config or > 50 MB log; abort with explicit message. |

## 2. Out-of-scope threats (not mitigated by the skill)

The skill does **not** defend against:

- Compromise of the operator's machine or `fab` token cache.
- Malicious code inside notebooks that **runs in Fabric** after deployment. (The skill ships artifacts; it does not vet their runtime behavior.)
- Tampering with the FabricCLI repo itself (use git signed commits + branch protection).
- Network-level interception (mTLS to Fabric APIs is `fab`'s responsibility).
- Insider threats from the operator (deploying intentionally malicious code with full credentials).

## 3. Authentication & authorization model

- The skill **never** handles credentials directly. No tokens, no passwords, no SPN secrets are read into the skill's process memory.
- Authentication is delegated entirely to `fab auth login` (prior step) and the OS keychain / `fab`'s credential cache.
- Authorization is enforced server-side by Fabric — the skill cannot escalate privilege; it can only request what the operator is already entitled to.
- If the operator has only Contributor rights, `fab` returns 403 on Admin-scoped calls; the skill surfaces this via F-06 without retrying.
