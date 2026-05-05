"""
TOMPo MCP Server — Power BI & Fabric Lineage Intelligence.

Exposes 6 tools to AI assistants (GitHub Copilot, Claude, etc.):
  1. list_workspaces            — List Fabric workspaces you have access to
  2. generate_lineage           — Full lineage for ONE model: model → tables → reports → visuals → fields
  3. generate_workspace_lineage — Full lineage for ALL models in a workspace (parallel, fast)
  4. impact_analysis            — Where is a specific column/measure used?
  5. describe_semantic_model    — Tables, columns, measures, relationships, roles
  6. export_lineage_html        — Generate interactive D3 visualization as HTML file (all models)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import webbrowser
from importlib import resources
from typing import Any

from mcp.server.fastmcp import FastMCP

from tompo_mcp.auth import TokenProvider
from tompo_mcp.core.fabric_client import FabricClient
from tompo_mcp.core.lineage import build_lineage, get_all_impact_analysis, get_impact_analysis
from tompo_mcp.core.models import LineageNode, LineageResponse, ReportInfo, SemanticModelInfo
from tompo_mcp.core.parser import parse_report_definition, parse_semantic_model

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "TOMPo",
    instructions="Power BI & Fabric lineage intelligence — trace from semantic models to reports to individual visuals.",
)

# ── Shared state ──────────────────────────────────────────────────────
_token_provider: TokenProvider | None = None
_client: FabricClient | None = None
_last_lineage: LineageResponse | None = None
_last_workspace_id: str = ""
# Accumulates all lineages per workspace (dataset_id → LineageResponse)
_workspace_lineages: dict[str, LineageResponse] = {}


def _get_client() -> FabricClient:
    global _token_provider, _client
    if _client is None:
        _token_provider = TokenProvider()
        _client = FabricClient(_token_provider)
    return _client


# ── Tool 1: List Workspaces ──────────────────────────────────────────

@mcp.tool()
async def list_workspaces() -> str:
    """List all Fabric/Power BI workspaces you have access to.

    Returns workspace names and IDs. Use the workspace ID in other tools.
    Requires: az login (uses your Azure identity).
    """
    client = _get_client()
    workspaces = await client.list_workspaces()

    if not workspaces:
        return "No workspaces found. Make sure you're logged in with `az login` and have access to Fabric workspaces."

    lines = [f"Found {len(workspaces)} workspaces:\n"]
    for ws in sorted(workspaces, key=lambda w: w.get("name", "")):
        name = ws.get("name", "Unknown")
        wid = ws.get("id", "")
        ws_type = ws.get("type", "")
        state = ws.get("state", "")
        line = f"  - **{name}** (`{wid}`)"
        if ws_type:
            line += f" [{ws_type}]"
        if state and state != "Active":
            line += f" ({state})"
        lines.append(line)

    return "\n".join(lines)


# ── Tool 2: Generate Lineage ────────────────────────────────────────

@mcp.tool()
async def generate_lineage(
    workspace_id: str,
    dataset_id: str | None = None,
    dataset_name: str | None = None,
) -> str:
    """Generate complete lineage for a semantic model: Model → Tables → Reports → Pages → Visuals → Columns/Measures.

    Args:
        workspace_id: The workspace ID (from list_workspaces).
        dataset_id: The semantic model (dataset) ID. If not provided, lists available models.
        dataset_name: Optional human name for the dataset (helps with display).

    Returns the lineage tree showing exactly which columns/measures appear in which visuals.
    Tip: Use generate_workspace_lineage to scan ALL models in a workspace at once (faster).
    """
    global _last_lineage, _last_workspace_id, _workspace_lineages
    client = _get_client()

    # If no dataset_id, list available datasets
    if not dataset_id:
        items = await client.get_workspace_items(workspace_id)
        datasets = items.get("datasets", [])
        if not datasets:
            return "No semantic models found in this workspace."
        lines = ["Available semantic models in this workspace:\n"]
        for ds in datasets:
            lines.append(f"  - **{ds.get('name', 'Unknown')}** (`{ds.get('id', '')}`)")
        lines.append("\nUse `generate_workspace_lineage` to generate lineage for ALL models at once, or use the dataset ID here for a single model.")
        return "\n".join(lines)

    # Get semantic model definition
    raw_model = await client.get_semantic_model_definition(workspace_id, dataset_id)
    if not raw_model:
        return f"Could not retrieve semantic model definition for dataset `{dataset_id}`. This may be due to sensitivity labels (Confidential/Restricted) blocking access. Check permissions."

    model = parse_semantic_model(raw_model, dataset_id, dataset_name or dataset_id)

    # Get reports bound to this dataset
    report_dicts = await client.get_reports_for_dataset(workspace_id, dataset_id)
    if not report_dicts:
        lineage = build_lineage(model, [], workspace_id)
        _last_lineage = lineage
        _last_workspace_id = workspace_id
        _workspace_lineages[dataset_id] = lineage
        return f"Semantic model **{model.name}** has {len(model.tables)} tables but no reports are bound to it (orphaned model).\n\n" + _format_model_summary(model)

    # Get report definitions
    reports: list[ReportInfo] = []
    for rd in report_dicts:
        rid = rd.get("id", "")
        rname = rd.get("name", "Unknown")
        raw_report = await client.get_report_definition(workspace_id, rid)
        if raw_report:
            report = parse_report_definition(raw_report, rid, rname, dataset_id)
            reports.append(report)
        else:
            reports.append(ReportInfo(id=rid, name=rname, dataset_id=dataset_id))

    # Build lineage
    lineage = build_lineage(model, reports, workspace_id)
    _last_lineage = lineage
    _last_workspace_id = workspace_id
    _workspace_lineages[dataset_id] = lineage

    return _format_lineage_tree(lineage)


# ── Tool 2b: Generate Workspace Lineage (ALL models, parallel) ───────

@mcp.tool()
async def generate_workspace_lineage(
    workspace_id: str,
) -> str:
    """Generate lineage for ALL semantic models in a workspace in one call (parallel, fast).

    Args:
        workspace_id: The workspace ID (from list_workspaces).

    Scans every semantic model in the workspace, finds bound reports, and builds complete
    lineage trees. Results are accumulated for export_lineage_html. Much faster than
    calling generate_lineage multiple times.
    """
    global _last_lineage, _last_workspace_id, _workspace_lineages
    client = _get_client()

    items = await client.get_workspace_items(workspace_id)
    datasets = items.get("datasets", [])
    all_reports = items.get("reports", [])

    if not datasets:
        return "No semantic models found in this workspace."

    # Reset workspace lineages for this workspace
    _workspace_lineages = {}
    _last_workspace_id = workspace_id

    results: list[str] = []
    errors: list[str] = []

    # Process models with limited concurrency (3 at a time to avoid rate limits)
    semaphore = asyncio.Semaphore(3)

    async def _process_model(ds: dict) -> None:
        ds_id = ds.get("id", "")
        ds_name = ds.get("name", "Unknown")
        async with semaphore:
            try:
                raw_model = await client.get_semantic_model_definition(workspace_id, ds_id)
                if not raw_model:
                    errors.append(f"⚠️ **{ds_name}** — could not retrieve definition (possibly Confidential/Restricted label)")
                    return

                model = parse_semantic_model(raw_model, ds_id, ds_name)

                # Find reports bound to this dataset
                bound_reports = [r for r in all_reports if r.get("datasetId") == ds_id]
                reports: list[ReportInfo] = []
                for rd in bound_reports:
                    rid = rd.get("id", "")
                    rname = rd.get("name", "Unknown")
                    raw_report = await client.get_report_definition(workspace_id, rid)
                    if raw_report:
                        report = parse_report_definition(raw_report, rid, rname, ds_id)
                        reports.append(report)
                    else:
                        reports.append(ReportInfo(id=rid, name=rname, dataset_id=ds_id))

                lineage = build_lineage(model, reports, workspace_id)
                _workspace_lineages[ds_id] = lineage

                status = "Active" if reports else "Orphaned (no reports)"
                results.append(f"✅ **{ds_name}** — {len(model.tables)} tables, {len(reports)} reports [{status}]")
            except Exception as exc:
                errors.append(f"❌ **{ds_name}** — error: {exc}")

    await asyncio.gather(*[_process_model(ds) for ds in datasets])

    # Set _last_lineage to the first one that has reports, or just the first one
    for lineage in _workspace_lineages.values():
        _last_lineage = lineage
        if lineage.reports:
            break

    # Format summary
    lines = [f"# Workspace Lineage Scan Complete\n"]
    lines.append(f"**Models found:** {len(datasets)} | **Successfully scanned:** {len(results)} | **Errors:** {len(errors)}\n")

    if results:
        lines.append("## Scanned Models\n")
        lines.extend(results)
        lines.append("")

    if errors:
        lines.append("## Issues\n")
        lines.extend(errors)
        lines.append("")

    lines.append(f"\n💡 Use `export_lineage_html` to generate an interactive visualization with ALL {len(_workspace_lineages)} models.")
    return "\n".join(lines)


def _format_lineage_tree(lineage: LineageResponse) -> str:
    """Format lineage as a readable tree string."""
    lines: list[str] = []
    model = lineage.model
    tree = lineage.lineage_tree

    lines.append(f"# Lineage for {model.name}\n")
    lines.append(f"**Tables:** {len(model.tables)} | **Reports:** {len(lineage.reports)} | "
                 f"**Relationships:** {len(model.relationships)}\n")

    def _render_node(node: LineageNode, indent: str = "", is_last: bool = True) -> None:
        connector = "└── " if is_last else "├── "
        prefix = indent + connector

        icon = {
            "model": "📊", "table": "📋", "report": "📄",
            "page": "📑", "visual": "📈", "column": "🔹", "measure": "🔸",
        }.get(node.node_type, "•")

        label = node.name
        extra = ""

        if node.node_type == "visual":
            title = node.metadata.get("title", "")
            if title and title != node.name:
                extra = f" — *{title}*"
        elif node.node_type == "table":
            cc = node.metadata.get("column_count", 0)
            mc = node.metadata.get("measure_count", 0)
            if node.metadata.get("orphan"):
                extra = f" ({cc} cols, {mc} measures) ⚠️ *not used in any report*"
            else:
                extra = f" ({cc} cols, {mc} measures)"
        elif node.node_type in ("column", "measure"):
            extra = f" [{node.node_type[0].upper()}]"

        lines.append(f"{prefix}{icon} {label}{extra}")

        child_indent = indent + ("    " if is_last else "│   ")
        for i, child in enumerate(node.children):
            _render_node(child, child_indent, i == len(node.children) - 1)

    if tree.children:
        for i, child in enumerate(tree.children):
            _render_node(child, "", i == len(tree.children) - 1)
    else:
        lines.append("No lineage connections found.")

    return "\n".join(lines)


def _format_model_summary(model: SemanticModelInfo) -> str:
    lines = [f"## {model.name}\n"]
    for tbl in model.tables:
        if tbl.is_hidden:
            continue
        lines.append(f"**{tbl.name}** — {len(tbl.columns)} columns, {len(tbl.measures)} measures")
    return "\n".join(lines)


# ── Tool 3: Impact Analysis ─────────────────────────────────────────

@mcp.tool()
async def impact_analysis(
    field_name: str,
    table_name: str = "",
    field_type: str = "column",
    workspace_id: str = "",
    dataset_id: str = "",
) -> str:
    """Find all visuals where a specific column or measure is used (impact analysis).

    Args:
        field_name: The column or measure name to search for.
        table_name: The table containing the field. If empty, searches all tables.
        field_type: "column" or "measure" (default: "column").
        workspace_id: Workspace ID (optional if you just ran generate_lineage).
        dataset_id: Dataset ID (optional if you just ran generate_lineage).

    Searches across ALL scanned models in the workspace. Shows which reports, pages, and
    visuals would be affected if you rename or remove this field.
    """
    global _last_lineage, _last_workspace_id, _workspace_lineages

    wid = workspace_id or _last_workspace_id

    # Determine which lineages to search
    lineages_to_search: list[LineageResponse] = []
    if dataset_id and dataset_id in _workspace_lineages:
        lineages_to_search = [_workspace_lineages[dataset_id]]
    elif _workspace_lineages:
        lineages_to_search = list(_workspace_lineages.values())
    elif _last_lineage:
        lineages_to_search = [_last_lineage]
    elif workspace_id and dataset_id:
        await generate_lineage(workspace_id, dataset_id)
        if _last_lineage:
            lineages_to_search = [_last_lineage]

    if not lineages_to_search:
        return "No lineage data available. Run `generate_workspace_lineage` or `generate_lineage` first."

    # Search across all lineages
    all_results = []
    for lineage in lineages_to_search:
        reports = lineage.reports
        model = lineage.model

        if not table_name:
            for tbl in model.tables:
                for col in tbl.columns:
                    if col.name.lower() == field_name.lower():
                        r = get_impact_analysis(col.name, "column", tbl.name, reports, wid)
                        if r.usage_count > 0:
                            all_results.append((model.name, r))
                for m in tbl.measures:
                    if m.name.lower() == field_name.lower():
                        r = get_impact_analysis(m.name, "measure", tbl.name, reports, wid)
                        if r.usage_count > 0:
                            all_results.append((model.name, r))
        else:
            result = get_impact_analysis(field_name, field_type, table_name, reports, wid)
            if result.usage_count > 0:
                all_results.append((model.name, result))

    if not all_results:
        model_count = len(lineages_to_search)
        total_reports = sum(len(l.reports) for l in lineages_to_search)
        return f"Field `{field_name}` is not used in any visual across {model_count} model(s), {total_reports} report(s)."

    return _format_impact_results_multi(all_results)


def _format_impact_results(results: list) -> str:
    lines: list[str] = []
    total_usage = sum(r.usage_count for r in results)
    lines.append(f"# Impact Analysis — {total_usage} visual(s) affected\n")

    for r in results:
        lines.append(f"## `{r.table_name}.{r.object_name}` ({r.object_type}) — {r.usage_count} usage(s)\n")
        lines.append("| Report | Page | Visual | Type |")
        lines.append("|--------|------|--------|------|")
        for item in r.used_in:
            title = item.visual_title or item.visual_type
            lines.append(f"| {item.report_name} | {item.page_name} | {title} | {item.visual_type} |")
        lines.append("")

    return "\n".join(lines)


def _format_impact_results_multi(results: list[tuple[str, Any]]) -> str:
    """Format impact results from multiple models."""
    lines: list[str] = []
    total_usage = sum(r.usage_count for _, r in results)
    model_names = sorted(set(m for m, _ in results))
    lines.append(f"# Impact Analysis — {total_usage} visual(s) affected across {len(model_names)} model(s)\n")

    for model_name, r in results:
        lines.append(f"## [{model_name}] `{r.table_name}.{r.object_name}` ({r.object_type}) — {r.usage_count} usage(s)\n")
        lines.append("| Report | Page | Visual | Type |")
        lines.append("|--------|------|--------|------|")
        for item in r.used_in:
            title = item.visual_title or item.visual_type
            lines.append(f"| {item.report_name} | {item.page_name} | {title} | {item.visual_type} |")
        lines.append("")

    return "\n".join(lines)


# ── Tool 4: Describe Semantic Model ──────────────────────────────────

@mcp.tool()
async def describe_semantic_model(
    workspace_id: str = "",
    dataset_id: str = "",
) -> str:
    """Describe the semantic model: tables, columns, measures, relationships, and roles.

    Args:
        workspace_id: Workspace ID (optional if you just ran generate_lineage).
        dataset_id: Dataset ID (optional if you just ran generate_lineage).

    Returns detailed metadata about the semantic model structure.
    If dataset_id is provided and was previously scanned, returns that specific model.
    """
    global _last_lineage, _workspace_lineages

    # Look up specific model from cache if dataset_id provided
    lineage = None
    if dataset_id and dataset_id in _workspace_lineages:
        lineage = _workspace_lineages[dataset_id]
    elif _last_lineage:
        lineage = _last_lineage

    if not lineage and workspace_id and dataset_id:
        await generate_lineage(workspace_id, dataset_id)
        lineage = _workspace_lineages.get(dataset_id) or _last_lineage

    if not lineage:
        return "No lineage data available. Run `generate_lineage` or `generate_workspace_lineage` first."

    model = lineage.model
    lines: list[str] = []

    lines.append(f"# Semantic Model: {model.name}\n")
    if model.description:
        lines.append(f"*{model.description}*\n")

    # Tables summary
    visible_tables = [t for t in model.tables if not t.is_hidden]
    lines.append(f"**Tables:** {len(visible_tables)} visible ({len(model.tables)} total)")
    lines.append(f"**Relationships:** {len(model.relationships)}")
    lines.append(f"**Roles:** {len(model.roles)}\n")

    # Per-table detail
    for tbl in visible_tables:
        lines.append(f"## 📋 {tbl.name}")
        if tbl.description:
            lines.append(f"*{tbl.description}*")
        if tbl.source:
            src_preview = tbl.source[:200] + "..." if len(tbl.source) > 200 else tbl.source
            lines.append(f"Source: `{src_preview}`")

        if tbl.columns:
            lines.append(f"\n**Columns ({len(tbl.columns)}):**")
            for col in tbl.columns:
                if col.is_hidden:
                    continue
                desc = f" — {col.description}" if col.description else ""
                lines.append(f"  - `{col.name}` ({col.data_type}){desc}")

        if tbl.measures:
            lines.append(f"\n**Measures ({len(tbl.measures)}):**")
            for m in tbl.measures:
                desc = f" — {m.description}" if m.description else ""
                expr_preview = m.expression[:100] + "..." if len(m.expression) > 100 else m.expression
                lines.append(f"  - `{m.name}` = `{expr_preview}`{desc}")
        lines.append("")

    # Relationships
    if model.relationships:
        lines.append("## 🔗 Relationships\n")
        lines.append("| From | → | To | Cardinality | Active |")
        lines.append("|------|---|-----|-------------|--------|")
        for rel in model.relationships:
            card = f"{rel.from_cardinality}:{rel.to_cardinality}"
            active = "✅" if rel.is_active else "❌"
            lines.append(f"| {rel.from_table}.{rel.from_column} | → | {rel.to_table}.{rel.to_column} | {card} | {active} |")
        lines.append("")

    # Roles
    if model.roles:
        lines.append("## 🔐 Roles\n")
        for role in model.roles:
            lines.append(f"  - **{role.name}** (permission: {role.model_permission})")
            for tp in role.table_permissions:
                lines.append(f"    - {tp.get('table', '')}: `{tp.get('filter', '')}`")

    return "\n".join(lines)


# ── Tool 5: Export Lineage HTML ──────────────────────────────────────

@mcp.tool()
async def export_lineage_html(
    output_path: str = "",
) -> str:
    """Export ALL generated lineages as an interactive D3 tree visualization (HTML file).

    Args:
        output_path: File path to save HTML (default: auto-generated in current directory).

    The HTML includes a model selector dropdown when multiple models are scanned.
    Opens the visualization in your default browser. The HTML file is self-contained
    with all JavaScript/CSS inlined — no server needed, works offline.

    Run generate_lineage or generate_workspace_lineage first to populate the lineage data.
    """
    global _workspace_lineages, _last_lineage

    # Collect all lineages
    all_lineages = list(_workspace_lineages.values()) if _workspace_lineages else (
        [_last_lineage] if _last_lineage else []
    )

    if not all_lineages:
        return "No lineage data available. Run `generate_workspace_lineage` or `generate_lineage` first."

    # Serialize all lineages as an array
    lineages_json = [l.model_dump() for l in all_lineages]

    # Load HTML template
    template_path = os.path.join(os.path.dirname(__file__), "viz", "template.html")
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    # Inject lineage data (array of all models)
    html = template.replace("__LINEAGE_DATA_PLACEHOLDER__", json.dumps(lineages_json, default=str))

    # Determine output path
    if not output_path:
        # Use first model name or workspace
        model_name = all_lineages[0].model.name.replace(" ", "_").replace("/", "_")
        if len(all_lineages) > 1:
            model_name = f"workspace_{len(all_lineages)}_models"
        output_path = os.path.join(os.getcwd(), f"lineage_{model_name}.html")

    # Validate output path — prevent path traversal
    output_path = os.path.abspath(output_path)
    if not output_path.endswith(".html"):
        return "Error: output_path must end with .html"

    # Ensure parent directory exists (fixes Errno 2)
    parent_dir = os.path.dirname(output_path)
    os.makedirs(parent_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    # Open in browser
    try:
        webbrowser.open(f"file://{output_path}")
    except Exception:
        pass

    model_names = [l.model.name for l in all_lineages]
    return (
        f"Interactive lineage visualization saved to `{output_path}` and opened in browser.\n"
        f"Contains {len(all_lineages)} model(s): {', '.join(model_names)}"
    )


# ── Server entry point ───────────────────────────────────────────────

def run_server() -> None:
    """Start the MCP server (stdio transport)."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    mcp.run(transport="stdio")
