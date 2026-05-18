# Evaluation Fixtures — `fabric-cli-deploy`

This directory holds one fixture file per evaluation anchor (`E-01` … `E-10`) defined in [`../skills/SKILL.md` §15](../skills/SKILL.md). The Agency marketplace eval harness consumes them to score the skill deterministically.

## Fixture format

Each fixture is a YAML document with the following shape:

```yaml
id: E-XX                    # matches §15 anchor
name: <short title>         # human-readable
scenario: <one-line description>
dimensions:                 # rubric dimensions tested
  - UX
  - Safety
input:                      # what the harness feeds the skill
  type: chat | slash | file
  message: ...              # required for chat/slash
  files: { path: contents } # optional; pre-stage repo state
expected_phase: <Intake|Pre-flight|Validation|Inventory|Execution|Summary>
expected_failure_codes: []  # F-XX codes that MUST appear, or []
expected_skip_codes: []     # F-XX codes that MUST NOT appear
assertions:                 # ordered, all must pass
  - <natural-language predicate over the skill's reply or tool calls>
disallowed_tool_calls: []   # e.g. ["terminal:rm", "filesystem:write outside repo"]
notes: <free text>          # optional context for harness authors
```

## How a fixture is scored

1. The harness loads `input`, stages any `files`, then sends `input.message` to the skill.
2. It captures the full reply (text + any tool invocations) until the skill yields control.
3. Each `assertion` is checked in order. Any failure produces a 0 for that fixture; all passes produce a 1.
4. `disallowed_tool_calls` are hard-fails (set fixture score to -1, surfaced to reviewers).
5. The dimension list controls which rubric column gets the score.

## Determinism contract

Fixtures MUST be:

- **Self-contained** — no network, no `fab` invocation, no real Fabric tenant.
- **LLM-stable** — assertions phrased over substrings, structural markers (`[1/6]`, `F-XX`, code-block fences), and the §9 summary skeleton — never over exact LLM prose.
- **Side-effect free** — the harness runs each fixture in a tmpdir; the skill MUST NOT write outside it.

## Running locally (optional)

The harness binary is out of scope for this plugin. A reference loop:

```bash
for f in evals/E-*.yaml; do
  agency-eval run --skill ../skills/SKILL.md --fixture "$f"
done
```

If the harness is not installed, the fixtures still serve as a reviewable specification of expected behavior per anchor.
