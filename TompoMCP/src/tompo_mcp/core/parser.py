"""
Report and semantic model definition parser (standalone — no FastAPI dependency).

Parses PBIR, legacy Layout, TMSL/BIM, TMDL, Scanner API, and DAX INFO outputs.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from tompo_mcp.core.models import (
    ColumnInfo,
    MeasureInfo,
    PageInfo,
    RelationshipInfo,
    ReportInfo,
    RoleInfo,
    RoleMember,
    SemanticModelInfo,
    TableInfo,
    VisualFieldBinding,
    VisualInfo,
)

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════
# SEMANTIC MODEL PARSING
# ═════════════════════════════════════════════════════════════════════════


def parse_semantic_model(
    raw_definition: dict[str, Any], dataset_id: str, dataset_name: str
) -> SemanticModelInfo:
    source = raw_definition.get("_source", "")
    if source == "scanner":
        return _parse_from_scanner(raw_definition, dataset_id, dataset_name)
    if source == "dax":
        return _parse_from_dax(raw_definition, dataset_id, dataset_name)
    return _parse_from_fabric_definition(raw_definition, dataset_id, dataset_name)


def _parse_from_fabric_definition(
    definition: dict[str, Any], dataset_id: str, dataset_name: str
) -> SemanticModelInfo:
    bim_content = None
    for key, value in definition.items():
        if key.endswith("model.bim") or key.endswith(".bim"):
            bim_content = value
            break
        if isinstance(value, dict) and "model" in value:
            bim_content = value
            break

    if bim_content and isinstance(bim_content, dict):
        return _parse_bim_json(bim_content, dataset_id, dataset_name)

    tmdl_parts = {k: v for k, v in definition.items() if isinstance(v, str) and k.endswith(".tmdl")}
    if tmdl_parts:
        return _parse_tmdl(tmdl_parts, dataset_id, dataset_name)

    for key, value in definition.items():
        if isinstance(value, dict):
            if "tables" in value or "model" in value:
                return _parse_bim_json(
                    value if "model" in value else {"model": value},
                    dataset_id, dataset_name,
                )

    logger.warning("Could not detect semantic model format, returning empty model")
    return SemanticModelInfo(id=dataset_id, name=dataset_name)


def _parse_bim_json(
    bim: dict[str, Any], dataset_id: str, dataset_name: str
) -> SemanticModelInfo:
    model = bim.get("model", bim)

    tables: list[TableInfo] = []
    for tbl in model.get("tables", []):
        columns = [
            ColumnInfo(
                name=col.get("name", ""),
                data_type=col.get("dataType", "Unknown"),
                is_hidden=col.get("isHidden", False),
                expression=col.get("expression"),
                description=col.get("description"),
                source_column=col.get("sourceColumn"),
            )
            for col in tbl.get("columns", [])
        ]
        measures = [
            MeasureInfo(
                name=m.get("name", ""),
                expression=_normalize_expression(m.get("expression", "")),
                format_string=m.get("formatString"),
                description=m.get("description"),
                table_name=tbl.get("name", ""),
            )
            for m in tbl.get("measures", [])
        ]

        source = None
        for part in tbl.get("partitions", []):
            src = part.get("source", {})
            if src.get("type") == "m":
                expr = src.get("expression")
                if isinstance(expr, list):
                    source = "\n".join(expr)
                elif isinstance(expr, str):
                    source = expr
                break

        tables.append(
            TableInfo(
                name=tbl.get("name", ""),
                is_hidden=tbl.get("isHidden", False),
                description=tbl.get("description"),
                source=source,
                columns=columns,
                measures=measures,
            )
        )

    relationships = [
        RelationshipInfo(
            from_table=rel.get("fromTable", ""),
            from_column=rel.get("fromColumn", ""),
            to_table=rel.get("toTable", ""),
            to_column=rel.get("toColumn", ""),
            from_cardinality=str(rel.get("fromCardinality", "many")),
            to_cardinality=str(rel.get("toCardinality", "one")),
            cross_filter=str(rel.get("crossFilteringBehavior", "oneDirection")),
            is_active=rel.get("isActive", True),
        )
        for rel in model.get("relationships", [])
    ]

    roles = [
        RoleInfo(
            name=role.get("name", ""),
            model_permission=str(role.get("modelPermission", "read")),
            table_permissions=[
                {"table": tp.get("name", ""), "filter": tp.get("filterExpression", "")}
                for tp in role.get("tablePermissions", [])
            ],
            members=[
                RoleMember(member_name=m.get("memberName", ""))
                for m in role.get("members", [])
            ],
        )
        for role in model.get("roles", [])
    ]

    return SemanticModelInfo(
        id=dataset_id,
        name=dataset_name,
        description=model.get("description"),
        tables=tables,
        relationships=relationships,
        roles=roles,
    )


def _parse_tmdl(
    tmdl_parts: dict[str, str], dataset_id: str, dataset_name: str
) -> SemanticModelInfo:
    tables: list[TableInfo] = []
    relationships: list[RelationshipInfo] = []
    roles: list[RoleInfo] = []

    for path, content in tmdl_parts.items():
        if "/tables/" in path or path.startswith("tables/"):
            table = _parse_tmdl_table(content)
            if table:
                tables.append(table)
        elif "/relationships/" in path or path.startswith("relationships/"):
            rel = _parse_tmdl_relationship(content)
            if rel:
                relationships.append(rel)
        elif "/roles/" in path or path.startswith("roles/"):
            role = _parse_tmdl_role(content)
            if role:
                roles.append(role)

    for path, content in tmdl_parts.items():
        if path.endswith("model.tmdl") or path == "model.tmdl":
            inline_rels, inline_roles = _parse_tmdl_model_file(content, tables)
            relationships.extend(inline_rels)
            roles.extend(inline_roles)

    return SemanticModelInfo(
        id=dataset_id, name=dataset_name,
        tables=tables, relationships=relationships, roles=roles,
    )


def _parse_tmdl_table(content: str) -> Optional[TableInfo]:
    lines = content.split("\n")
    table_name = ""
    columns: list[ColumnInfo] = []
    measures: list[MeasureInfo] = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("table "):
            table_name = line.replace("table ", "").strip().strip("'\"")
        elif line.startswith("column "):
            col_name = line.replace("column ", "").strip().strip("'\"")
            data_type = "Unknown"
            i += 1
            while i < len(lines) and lines[i].startswith("\t\t"):
                prop = lines[i].strip()
                if prop.startswith("dataType:"):
                    data_type = prop.replace("dataType:", "").strip()
                i += 1
            columns.append(ColumnInfo(name=col_name, data_type=data_type))
            continue
        elif line.startswith("measure "):
            match = re.match(r"measure\s+'?([^'=]+)'?\s*=\s*(.*)", line)
            if match:
                m_name = match.group(1).strip()
                m_expr = match.group(2).strip()
                i += 1
                while i < len(lines) and (lines[i].startswith("\t\t\t") or lines[i].strip() == ""):
                    m_expr += "\n" + lines[i].strip()
                    i += 1
                measures.append(MeasureInfo(name=m_name, expression=m_expr, table_name=table_name))
                continue
        i += 1

    if not table_name:
        return None
    return TableInfo(name=table_name, columns=columns, measures=measures)


def _parse_tmdl_relationship(content: str) -> Optional[RelationshipInfo]:
    from_table = from_column = to_table = to_column = ""
    from_card = "many"
    to_card = "one"
    cross_filter = "oneDirection"
    is_active = True

    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("fromColumn:"):
            ref = stripped.replace("fromColumn:", "").strip().strip("'\"")
            parts = ref.split(".")
            if len(parts) >= 2:
                from_table = parts[0].strip("'\"")
                from_column = ".".join(parts[1:]).strip("'\"")
            else:
                from_column = ref
        elif stripped.startswith("toColumn:"):
            ref = stripped.replace("toColumn:", "").strip().strip("'\"")
            parts = ref.split(".")
            if len(parts) >= 2:
                to_table = parts[0].strip("'\"")
                to_column = ".".join(parts[1:]).strip("'\"")
            else:
                to_column = ref
        elif stripped.startswith("fromCardinality:"):
            from_card = stripped.replace("fromCardinality:", "").strip()
        elif stripped.startswith("toCardinality:"):
            to_card = stripped.replace("toCardinality:", "").strip()
        elif stripped.startswith("crossFilteringBehavior:"):
            cross_filter = stripped.replace("crossFilteringBehavior:", "").strip()
        elif stripped.startswith("isActive:"):
            is_active = stripped.replace("isActive:", "").strip().lower() != "false"

    if not (from_table and to_table):
        return None
    return RelationshipInfo(
        from_table=from_table, from_column=from_column,
        to_table=to_table, to_column=to_column,
        from_cardinality=from_card, to_cardinality=to_card,
        cross_filter=cross_filter, is_active=is_active,
    )


def _parse_tmdl_role(content: str) -> Optional[RoleInfo]:
    role_name = ""
    model_permission = "read"
    table_permissions: list[dict[str, str]] = []
    members: list[RoleMember] = []

    lines = content.split("\n")
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("role "):
            role_name = stripped.replace("role ", "").strip().strip("'\"")
        elif stripped.startswith("modelPermission:"):
            model_permission = stripped.replace("modelPermission:", "").strip()
        elif stripped.startswith("tablePermission "):
            tp_table = stripped.replace("tablePermission ", "").strip().strip("'\"")
            filter_expr = ""
            i += 1
            while i < len(lines) and (lines[i].startswith("\t\t\t") or lines[i].startswith("   ")):
                sub = lines[i].strip()
                if sub.startswith("filterExpression:") or sub.startswith("expression:"):
                    filter_expr = sub.split(":", 1)[1].strip().strip('"')
                elif filter_expr == "" and not sub.startswith("//"):
                    filter_expr += sub
                i += 1
            table_permissions.append({"table": tp_table, "filter": filter_expr})
            continue
        elif stripped.startswith("member "):
            member_name = stripped.replace("member ", "").strip().strip("'\"")
            members.append(RoleMember(member_name=member_name))
        i += 1

    if not role_name:
        return None
    return RoleInfo(
        name=role_name, model_permission=model_permission,
        table_permissions=table_permissions, members=members,
    )


def _parse_tmdl_model_file(
    content: str, tables: list[TableInfo]
) -> tuple[list[RelationshipInfo], list[RoleInfo]]:
    relationships: list[RelationshipInfo] = []
    roles: list[RoleInfo] = []

    lines = content.split("\n")
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("relationship "):
            block = stripped + "\n"
            i += 1
            while i < len(lines) and (lines[i].startswith("\t") or lines[i].startswith("  ")):
                block += lines[i] + "\n"
                i += 1
            rel = _parse_tmdl_relationship(block)
            if rel:
                relationships.append(rel)
            continue
        if stripped.startswith("role "):
            block = stripped + "\n"
            i += 1
            while i < len(lines) and (lines[i].startswith("\t") or lines[i].startswith("  ")):
                block += lines[i] + "\n"
                i += 1
            role = _parse_tmdl_role(block)
            if role:
                roles.append(role)
            continue
        i += 1

    return relationships, roles


def _parse_from_scanner(
    raw: dict[str, Any], dataset_id: str, dataset_name: str
) -> SemanticModelInfo:
    ds = raw.get("dataset", {})
    tables = []
    for tbl in ds.get("tables", []):
        columns = [
            ColumnInfo(
                name=col.get("name", ""),
                data_type=col.get("columnType", "Unknown"),
                is_hidden=col.get("isHidden", False),
                description=col.get("description"),
            )
            for col in tbl.get("columns", [])
        ]
        measures = [
            MeasureInfo(
                name=m.get("name", ""),
                expression=m.get("expression", ""),
                description=m.get("description"),
                table_name=tbl.get("name", ""),
            )
            for m in tbl.get("measures", [])
        ]
        tables.append(
            TableInfo(
                name=tbl.get("name", ""),
                is_hidden=tbl.get("isHidden", False),
                description=tbl.get("description"),
                source=tbl.get("source", [{}])[0].get("expression") if tbl.get("source") else None,
                columns=columns, measures=measures,
            )
        )

    relationships = [
        RelationshipInfo(
            from_table=rel.get("fromTable", ""),
            from_column=rel.get("fromColumn", ""),
            to_table=rel.get("toTable", ""),
            to_column=rel.get("toColumn", ""),
            from_cardinality=str(rel.get("fromCardinality", "many")),
            to_cardinality=str(rel.get("toCardinality", "one")),
            cross_filter=str(rel.get("crossFilteringBehavior", "oneDirection")),
            is_active=rel.get("isActive", True),
        )
        for rel in ds.get("relationships", [])
    ]

    roles = [
        RoleInfo(
            name=role.get("name", ""),
            model_permission=str(role.get("modelPermission", "read")),
            table_permissions=[
                {"table": tp.get("name", ""), "filter": tp.get("filterExpression", "")}
                for tp in role.get("tablePermissions", [])
            ],
            members=[
                RoleMember(member_name=m.get("memberName", ""))
                for m in role.get("members", [])
            ],
        )
        for role in ds.get("roles", [])
    ]

    return SemanticModelInfo(
        id=dataset_id, name=ds.get("name", dataset_name),
        tables=tables, relationships=relationships, roles=roles,
    )


def _parse_from_dax(
    raw: dict[str, Any], dataset_id: str, dataset_name: str
) -> SemanticModelInfo:
    raw_tables = raw.get("tables", [])
    raw_columns = raw.get("columns", [])
    raw_measures = raw.get("measures", [])
    raw_relationships = raw.get("relationships", [])

    table_id_map: dict[int, str] = {}
    tables: list[TableInfo] = []

    for t in raw_tables:
        tid = t.get("[ID]", t.get("ID"))
        tname = t.get("[Name]", t.get("Name", ""))
        table_id_map[tid] = tname

        columns = [
            ColumnInfo(
                name=c.get("[ExplicitName]") or c.get("[InferredName]", ""),
                data_type=str(c.get("[ExplicitDataType]", "Unknown")),
                is_hidden=bool(c.get("[IsHidden]", False)),
                expression=c.get("[Expression]"),
                description=c.get("[Description]"),
            )
            for c in raw_columns
            if (c.get("[TableID]") or c.get("TableID")) == tid
        ]
        measures = [
            MeasureInfo(
                name=m.get("[Name]", m.get("Name", "")),
                expression=m.get("[Expression]", m.get("Expression", "")),
                format_string=m.get("[FormatString]", m.get("FormatString")),
                description=m.get("[Description]", m.get("Description")),
                table_name=tname,
            )
            for m in raw_measures
            if (m.get("[TableID]") or m.get("TableID")) == tid
        ]

        tables.append(
            TableInfo(
                name=tname,
                is_hidden=bool(t.get("[IsHidden]", False)),
                description=t.get("[Description]"),
                columns=columns, measures=measures,
            )
        )

    col_id_map: dict[int, tuple[int, str]] = {}
    for c in raw_columns:
        cid = c.get("[ID]") or c.get("ID")
        tid = c.get("[TableID]") or c.get("TableID")
        cname = c.get("[ExplicitName]") or c.get("[InferredName]", "")
        if cid is not None:
            col_id_map[cid] = (tid, cname)

    relationships = []
    for r in raw_relationships:
        from_col_id = r.get("[FromColumnID]") or r.get("FromColumnID")
        to_col_id = r.get("[ToColumnID]") or r.get("ToColumnID")
        from_tid, from_cname = col_id_map.get(from_col_id, (None, ""))
        to_tid, to_cname = col_id_map.get(to_col_id, (None, ""))
        relationships.append(
            RelationshipInfo(
                from_table=table_id_map.get(from_tid, ""),
                from_column=from_cname,
                to_table=table_id_map.get(to_tid, ""),
                to_column=to_cname,
                from_cardinality=str(r.get("[FromCardinality]", "many")),
                to_cardinality=str(r.get("[ToCardinality]", "one")),
                cross_filter=str(r.get("[CrossFilteringBehavior]", "oneDirection")),
                is_active=bool(r.get("[IsActive]", True)),
            )
        )

    raw_roles = raw.get("roles", [])
    roles = [
        RoleInfo(
            name=r.get("[Name]") or r.get("Name", ""),
            model_permission=str(r.get("[ModelPermission]") or r.get("ModelPermission", "read")),
        )
        for r in raw_roles
    ]

    return SemanticModelInfo(
        id=dataset_id, name=dataset_name,
        tables=tables, relationships=relationships, roles=roles,
    )


# ═════════════════════════════════════════════════════════════════════════
# REPORT / VISUAL PARSING
# ═════════════════════════════════════════════════════════════════════════


def parse_report_definition(
    raw_definition: dict[str, Any],
    report_id: str,
    report_name: str,
    dataset_id: Optional[str] = None,
) -> ReportInfo:
    source = raw_definition.get("_source", "")
    if source == "pages_api":
        return _parse_from_pages_api(raw_definition, report_id, report_name, dataset_id)

    pages = _try_parse_pbir(raw_definition, report_id, report_name, dataset_id)
    if pages:
        return ReportInfo(id=report_id, name=report_name, dataset_id=dataset_id, pages=pages)

    pages = _try_parse_legacy_layout(raw_definition, report_id, report_name, dataset_id)
    if pages:
        return ReportInfo(id=report_id, name=report_name, dataset_id=dataset_id, pages=pages)

    logger.warning("Could not parse report definition for %s", report_name)
    return ReportInfo(id=report_id, name=report_name, dataset_id=dataset_id)


def _try_parse_pbir(
    definition: dict[str, Any], report_id: str, report_name: str, dataset_id: Optional[str],
) -> Optional[list[PageInfo]]:
    page_paths: dict[str, dict[str, Any]] = {}
    visual_paths: dict[str, list[tuple[str, dict[str, Any]]]] = {}

    for path, content in definition.items():
        if not isinstance(content, dict):
            continue
        if "/pages/" in path and path.endswith("page.json"):
            page_id = path.split("/pages/")[1].split("/")[0]
            page_paths[page_id] = content
        if "/visuals/" in path and path.endswith("visual.json"):
            parts = path.split("/pages/")[1].split("/visuals/")
            if len(parts) == 2:
                page_id = parts[0]
                visual_paths.setdefault(page_id, []).append((path, content))

    if not page_paths:
        return None

    pages: list[PageInfo] = []
    for page_id, page_content in page_paths.items():
        display_name = page_content.get("displayName") or page_content.get("name") or page_id
        ordinal = page_content.get("ordinal", 0)
        visibility = page_content.get("visibility")

        visuals: list[VisualInfo] = []
        for _vpath, visual_content in visual_paths.get(page_id, []):
            visual_id = None
            try:
                vid_part = _vpath.split("/visuals/")[1]
                visual_id = vid_part.split("/")[0]
            except (IndexError, AttributeError):
                pass
            visual = _parse_pbir_visual(visual_content, visual_id=visual_id)
            if visual:
                visuals.append(visual)

        pages.append(PageInfo(
            name=page_id, display_name=display_name, ordinal=ordinal,
            visibility=str(visibility) if visibility else None, visuals=visuals,
        ))

    pages.sort(key=lambda p: p.ordinal)
    return pages


def _parse_pbir_visual(visual_content: dict[str, Any], visual_id: Optional[str] = None) -> Optional[VisualInfo]:
    v = visual_content.get("visual", visual_content)
    visual_type = v.get("visualType", "unknown")
    if visual_type in ("shape", "image", "textbox", "actionButton"):
        return None
    title = _extract_visual_title_pbir(v)
    field_bindings = _extract_field_bindings_pbir(v)
    return VisualInfo(visual_type=visual_type, title=title, visual_id=visual_id, field_bindings=field_bindings)


def _extract_visual_title_pbir(v: dict[str, Any]) -> Optional[str]:
    if "title" in v and isinstance(v["title"], str):
        return v["title"]

    objects = v.get("objects", {})
    title_obj = objects.get("title", [])
    if isinstance(title_obj, list):
        for t in title_obj:
            props = t.get("properties", {})
            text = props.get("text", {})
            if isinstance(text, dict):
                val = text.get("expr", {}).get("Literal", {}).get("Value", "")
                if val and val.startswith("'") and val.endswith("'"):
                    return val[1:-1]
                if val:
                    return val
            elif isinstance(text, str):
                return text

    vc_objects = v.get("vcObjects", {})
    title_items = vc_objects.get("title", [])
    if isinstance(title_items, list):
        for item in title_items:
            props = item.get("properties", {})
            title_text = props.get("titleText", {})
            if isinstance(title_text, dict):
                val = title_text.get("expr", {}).get("Literal", {}).get("Value", "")
                if val.startswith("'") and val.endswith("'"):
                    return val[1:-1]

    return None


def _extract_field_bindings_pbir(v: dict[str, Any]) -> list[VisualFieldBinding]:
    bindings: list[VisualFieldBinding] = []
    seen: set[tuple[str, str]] = set()

    # Method 1: dataTransforms.queryMetadata.Select
    data_transforms = v.get("dataTransforms", {})
    query_metadata = data_transforms.get("queryMetadata", {})
    for sel in query_metadata.get("Select", []):
        name = sel.get("Name", "")
        field_type_code = sel.get("Type")
        if "." in name:
            table_name, field_name = name.split(".", 1)
            field_type = "measure" if field_type_code == 2 else "column"
            key = (table_name, field_name)
            if key not in seen:
                seen.add(key)
                bindings.append(VisualFieldBinding(table_name=table_name, field_name=field_name, field_type=field_type))

    # Method 2: query.queryState projections
    query = v.get("query", {})
    query_state = query.get("queryState", {})
    for _role, role_data in query_state.items():
        projections = role_data.get("projections", []) if isinstance(role_data, dict) else []
        for proj in projections:
            query_ref = proj.get("queryRef", "")
            if "." in query_ref:
                table_name, field_name = query_ref.split(".", 1)
                key = (table_name, field_name)
                if key not in seen:
                    seen.add(key)
                    bindings.append(VisualFieldBinding(table_name=table_name, field_name=field_name, field_type="column"))

    # Method 3: prototypeQuery.Select
    prototype = v.get("prototypeQuery", {})
    for sel in prototype.get("Select", []):
        if "Column" in sel:
            col = sel["Column"]
            table_name = col.get("Expression", {}).get("SourceRef", {}).get("Entity", "")
            field_name = col.get("Property", "")
            if table_name and field_name:
                key = (table_name, field_name)
                if key not in seen:
                    seen.add(key)
                    bindings.append(VisualFieldBinding(table_name=table_name, field_name=field_name, field_type="column"))
        elif "Measure" in sel:
            meas = sel["Measure"]
            table_name = meas.get("Expression", {}).get("SourceRef", {}).get("Entity", "")
            field_name = meas.get("Property", "")
            if table_name and field_name:
                key = (table_name, field_name)
                if key not in seen:
                    seen.add(key)
                    bindings.append(VisualFieldBinding(table_name=table_name, field_name=field_name, field_type="measure"))

    return bindings


def _try_parse_legacy_layout(
    definition: dict[str, Any], report_id: str, report_name: str, dataset_id: Optional[str],
) -> Optional[list[PageInfo]]:
    layout_content = None
    for key, value in definition.items():
        if key.lower().endswith("layout") or key.lower() == "report/layout":
            layout_content = value
            break
        if isinstance(value, dict) and "sections" in value:
            layout_content = value
            break

    if not layout_content:
        return None
    if isinstance(layout_content, str):
        try:
            layout_content = json.loads(layout_content)
        except json.JSONDecodeError:
            return None

    sections = layout_content.get("sections", [])
    if not sections:
        return None

    pages: list[PageInfo] = []
    for idx, section in enumerate(sections):
        display_name = section.get("displayName", section.get("name", f"Page {idx + 1}"))
        visuals: list[VisualInfo] = []
        for vc in section.get("visualContainers", []):
            visual = _parse_legacy_visual_container(vc)
            if visual:
                visuals.append(visual)
        pages.append(PageInfo(
            name=section.get("name", f"section_{idx}"),
            display_name=display_name, ordinal=idx, visuals=visuals,
        ))
    return pages


def _parse_legacy_visual_container(vc: dict[str, Any]) -> Optional[VisualInfo]:
    config_str = vc.get("config", "")
    if isinstance(config_str, str):
        try:
            config = json.loads(config_str)
        except json.JSONDecodeError:
            return None
    else:
        config = config_str

    single_visual = config.get("singleVisual", {})
    if not single_visual:
        return None
    visual_type = single_visual.get("visualType", "unknown")
    if visual_type in ("shape", "image", "textbox", "actionButton"):
        return None
    visual_id = config.get("name")
    title = _extract_visual_title_legacy(single_visual)
    field_bindings = _extract_field_bindings_legacy(single_visual)
    return VisualInfo(visual_type=visual_type, title=title, visual_id=visual_id, field_bindings=field_bindings)


def _extract_visual_title_legacy(sv: dict[str, Any]) -> Optional[str]:
    vc_objects = sv.get("vcObjects", {})
    title_items = vc_objects.get("title", [])
    if isinstance(title_items, list):
        for item in title_items:
            props = item.get("properties", {})
            title_text = props.get("titleText", {})
            if isinstance(title_text, dict):
                val = title_text.get("expr", {}).get("Literal", {}).get("Value", "")
                if val.startswith("'") and val.endswith("'"):
                    return val[1:-1]
                if val:
                    return val
    return None


def _extract_field_bindings_legacy(sv: dict[str, Any]) -> list[VisualFieldBinding]:
    bindings: list[VisualFieldBinding] = []
    seen: set[tuple[str, str]] = set()

    prototype = sv.get("prototypeQuery", {})
    for sel in prototype.get("Select", []):
        table_name = ""
        field_name = ""
        field_type = "column"
        if "Column" in sel:
            col = sel["Column"]
            table_name = col.get("Expression", {}).get("SourceRef", {}).get("Entity", "")
            field_name = col.get("Property", "")
        elif "Measure" in sel:
            meas = sel["Measure"]
            table_name = meas.get("Expression", {}).get("SourceRef", {}).get("Entity", "")
            field_name = meas.get("Property", "")
            field_type = "measure"
        elif "Aggregation" in sel:
            agg = sel["Aggregation"]
            expr = agg.get("Expression", {})
            if "Column" in expr:
                col = expr["Column"]
                table_name = col.get("Expression", {}).get("SourceRef", {}).get("Entity", "")
                field_name = col.get("Property", "")
        if table_name and field_name:
            key = (table_name, field_name)
            if key not in seen:
                seen.add(key)
                bindings.append(VisualFieldBinding(table_name=table_name, field_name=field_name, field_type=field_type))

    projections = sv.get("projections", {})
    for _role, items in projections.items():
        if isinstance(items, list):
            for item in items:
                query_ref = item.get("queryRef", "")
                if "." in query_ref:
                    table_name, field_name = query_ref.split(".", 1)
                    key = (table_name, field_name)
                    if key not in seen:
                        seen.add(key)
                        bindings.append(VisualFieldBinding(table_name=table_name, field_name=field_name, field_type="column"))

    return bindings


def _parse_from_pages_api(
    raw: dict[str, Any], report_id: str, report_name: str, dataset_id: Optional[str]
) -> ReportInfo:
    pages = [
        PageInfo(
            name=p.get("name", ""),
            display_name=p.get("displayName", p.get("name", "")),
            ordinal=p.get("order", idx),
        )
        for idx, p in enumerate(raw.get("pages", []))
    ]
    return ReportInfo(id=report_id, name=report_name, dataset_id=dataset_id, pages=pages)


def _normalize_expression(expr: Any) -> str:
    if isinstance(expr, list):
        return "\n".join(expr)
    return str(expr) if expr else ""
