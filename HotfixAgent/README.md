# HotfixAgent

**AI-powered pipeline failure detection, root-cause analysis, and self-healing for Microsoft Fabric, Synapse Analytics, and Azure Data Factory.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Azure](https://img.shields.io/badge/cloud-Azure-0078D4.svg)](https://azure.microsoft.com/)
[![AI Foundry](https://img.shields.io/badge/agent-AI%20Foundry-0078D4.svg)](https://azure.microsoft.com/)

---

## What It Does

| Capability | Status | Description |
|---|---|---|
| **Checkpoint Onboarding** | Done | Wrap Fabric pipelines with checkpoint tracking — skip completed activities on re-run |
| **Multi-Agent RCA** | Done | AI Foundry agents classify failures, investigate root cause, notify Teams |
| **Pipeline Lineage** | Done | Trace activity execution across pipeline hierarchies |
| **Synapse Support** | Planned | Extend onboarding to Synapse Analytics pipelines |
| **ADF Support** | Planned | Extend onboarding to Azure Data Factory pipelines |

**Pattern**: `src/platforms/{platform}/{item_type}/{activity}/`

| Item Type | Activities |
|---|---|
| `notebooks/` | `onboarding/`, `shadow/`, `monitoring/` |
| `pipelines/` | `onboarding/`, `monitoring/` |
| `activators/` | `onboarding/`, `monitoring/` |

## Quick Start

### Prerequisites

- Python 3.10+
- Azure CLI (`az login`)
- Fabric workspace with Contributor access

### Install

```bash
git clone https://github.com/microsoft/HRDIUtilities.git
cd HotfixAgent
pip install -e ".[dev]"
```

### Configure

```bash
cp .env.example .env
# Edit .env with your workspace IDs and lakehouse name
```

### Onboard Pipelines (Dry Run)

**Option A: Notebook** (in Fabric)
1. Upload `src/platforms/fabric/notebooks/onboarding/OnboardPipelines_Checkpoint.ipynb` to your workspace
2. Set parameters and run with `DRY_RUN = True`

**Option B: CLI** (local)
```bash
python scripts/onboard.py \
  --workspace-id <GUID> \
  --lakehouse lh_pipeline_metadata \
  --dry-run
```

### Run Tests

```bash
pytest tests/unit/ -v
```

### Deploy Infrastructure

```bash
az deployment group create \
  --resource-group hotfix-agent-rg \
  --template-file infra/main.bicep \
  --parameters infra/parameters/dev.bicepparam
```

## How Checkpoint Onboarding Works

For each original activity `X`, the onboarding injects:

```
Original:   A → B → C

Modified:   _chk_load → _chk_var
             ↓
            _chk_if_A (skip if COMPLETED)
              True: A(retry=0) → _chk_upd_A | _chk_fail_A → _chk_re_fail_A
             ↓
            _chk_if_B ...
             ↓
            _chk_reset (clean slate on full success)
```

**On failure**: Error is captured in the checkpoint table, AI Foundry agent is notified, and the pipeline stops. On re-run, completed activities are skipped — only the failed activity re-executes.

## Multi-Agent System

| Agent | Role |
|---|---|
| **PipelineAgent** | Master orchestrator — classifies failure, routes to sub-agents, notifies Teams |
| **FabricDataAgent** | Data quality investigation — analyzes DQ rules, builds remediation SQL |
| **SWEAgent** | Creates Azure DevOps work items for code/schema fixes |
| **KBAgent** | Stores RCA findings as knowledge base articles for future reference |

## Platform Support

| Platform | Onboarding | Shadow | Monitoring | Agent |
|---|---|---|---|---|
| Microsoft Fabric | Done | Done | Done | Done |
| Synapse Analytics | Planned | Planned | Planned | Planned |
| Azure Data Factory | Planned | Planned | Planned | Planned |

## Documentation

- [Architecture](docs/architecture.md) — System diagram and component inventory
- [Onboarding Guide](docs/onboarding-guide.md) — Step-by-step pipeline onboarding
- [Agent Deployment](docs/agent-deployment.md) — AI Foundry agent setup
- [Troubleshooting](docs/troubleshooting.md) — Common issues and solutions

## Contributing

1. Create a feature branch from `main`
2. Make changes and add tests
3. Run `ruff check src/ tests/ scripts/` and `pytest tests/unit/`
4. Submit a PR using the [PR template](.azuredevops/pull_request_template.md)

<!-- ## License

[MIT](LICENSE) -->
