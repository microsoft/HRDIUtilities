# TOMPo MCP — Power BI & Fabric Lineage Intelligence

**Trace lineage from semantic models → tables → reports → pages → visuals → columns/measures.**

An MCP (Model Context Protocol) server that brings Power BI lineage intelligence directly into your AI assistant — GitHub Copilot, Claude Desktop, Cursor, or any MCP-compatible client.

## What it does

- **Full Lineage:** See exactly which columns and measures appear in which visuals, across all reports bound to a semantic model
- **Impact Analysis:** "What breaks if I rename `Employee.StartDate`?" — instantly shows every affected visual
- **Interactive Visualization:** Export a self-contained D3 tree (HTML file) with expand/collapse, zoom, and search
- **Zero Infrastructure:** Runs locally on your machine using your own Azure identity. No App Service, no Docker, no backend.

## Quick Start

### 1. Install

**Option A — Install directly from GitHub (recommended):**

```bash
pip install "git+https://github.com/microsoft/HRDIUtilities.git#subdirectory=TompoMCP"
```

**Option B — Clone and install locally:**

```bash
git clone https://github.com/microsoft/HRDIUtilities.git
cd HRDIUtilities/TompoMCP
pip install .
```

**Option C — Install from PyPI:**

```bash
pip install tompo-mcp
```

### 2. Login to Azure

```bash
az login
```

### 3. Add to VS Code

Open MCP config: `Ctrl+Shift+P` → **"MCP: Open User Configuration"** and add:

```json
{
  "servers": {
    "tompo": {
      "command": "python",
      "args": ["-m", "tompo_mcp"]
    }
  }
}
```

### 4. Use in Copilot Chat

Click the **Chat icon** (💬) in the VS Code sidebar, then ask:

```
> List my Fabric workspaces
> Generate lineage for dataset abc-123 in workspace xyz-456
> What visuals use the Employee.Department column?
> Export the lineage as an interactive HTML file
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `list_workspaces` | List all Fabric/Power BI workspaces you have access to |
| `generate_lineage` | Full lineage: Model → Tables → Reports → Pages → Visuals → Fields |
| `impact_analysis` | Find all visuals where a specific column or measure is used |
| `describe_semantic_model` | Detailed metadata: tables, columns, measures, relationships, roles |
| `export_lineage_html` | Generate interactive D3 visualization as a self-contained HTML file |

## How It Works

```
You type in Copilot Chat
        │
        ▼
Copilot calls TOMPo MCP tools
        │
        ▼
TOMPo runs locally on your machine:
  → Uses your az login identity
  → Calls Fabric REST APIs (getDefinition, Scanner, DAX)
  → Parses model + report definitions
  → Builds lineage tree
  → Returns data to Copilot
        │
        ▼
Copilot shows the lineage tree / impact table
(or opens interactive HTML in your browser)
```

### Authentication

TOMPo uses `DefaultAzureCredential` which automatically picks up:
1. **Azure CLI** (`az login`) — most common for developers
2. **VS Code Azure Account** — if you're signed into the Azure extension
3. **Environment variables** — for CI/CD pipelines
4. **Managed Identity** — for Azure-hosted scenarios

You need access to the Fabric workspaces you want to analyze. No extra app registrations or service principals required.

### Metadata Extraction (3-tier fallback)

1. **Fabric `getDefinition` API** — returns full model.bim / TMDL / PBIR definitions
2. **Admin Scanner API** — fallback if getDefinition fails (requires admin permissions)
3. **DAX `executeQueries`** — last resort using `INFO.TABLES()`, `INFO.COLUMNS()`, etc.

If a sensitivity label blocks access, TOMPo temporarily downgrades to "General", extracts metadata, then restores the original label.

## Interactive Visualization

The `export_lineage_html` tool generates a single HTML file with:
- **D3 horizontal tree** with expand/collapse nodes
- **Color-coded** by type (model, table, report, page, visual, column, measure)
- **Impact Analysis tab** with searchable data grid
- **Semantic Model tab** with tables, columns, measures, relationships
- **Zoom, pan, fullscreen** — all interactive
- **Works offline** — all JavaScript and CSS inlined, no server needed

## Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "tompo": {
      "command": "python",
      "args": ["-m", "tompo_mcp"]
    }
  }
}
```

## Development

```bash
git clone https://github.com/microsoft/HRDIUtilities.git
cd HRDIUtilities/TompoMCP
pip install -e .
python -m pytest tests/
```

## Requirements

- Python 3.10+
- Azure CLI (`az login`) or any Azure credential
- Access to Fabric/Power BI workspaces

## License

MIT
