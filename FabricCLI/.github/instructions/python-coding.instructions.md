---
applyTo: "**/*.py"
---

# Project coding standards for Python

Apply the [general coding guidelines](./general-coding.instructions.md) to all code.

## Python Guidelines

- Use snake_case for variable and function names
- Use CamelCase for class names
- Follow PEP 8 style guidelines
- Include type hints for function parameters and return types
- Write docstrings for all public modules, classes, functions, and methods
- Never use `shell=True`, `Invoke-Expression`, or `eval`. Construct subprocess
  arguments as `argv`-style lists and use `shell=False`.
- All user- or config-supplied values flowing into `subprocess`, `os`, or any
  filesystem path MUST first pass through `security_utils.validate_value()` or
  an equivalent allowlist regex check.
- Redact secret-shaped values in logs via `security_utils.redact_secrets()`
  before printing.
