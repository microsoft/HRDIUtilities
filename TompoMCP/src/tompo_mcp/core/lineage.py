"""Lineage builder — joins semantic model metadata with report visual field bindings."""

from __future__ import annotations

import logging

from tompo_mcp.core.links import build_report_link, build_visual_link
from tompo_mcp.core.models import (
    ImpactAnalysisResponse,
    ImpactItem,
    LineageNode,
    LineageResponse,
    ReportInfo,
    SemanticModelInfo,
)

logger = logging.getLogger(__name__)


def build_lineage(
    model: SemanticModelInfo,
    reports: list[ReportInfo],
    workspace_id: str = "",
) -> LineageResponse:
    tree = _build_lineage_tree(model, reports, workspace_id=workspace_id)
    return LineageResponse(model=model, reports=reports, lineage_tree=tree)


def _build_lineage_tree(
    model: SemanticModelInfo,
    reports: list[ReportInfo],
    workspace_id: str = "",
) -> LineageNode:
    model_node = LineageNode(
        name=model.name,
        node_type="model",
        metadata={"id": model.id, "table_count": len(model.tables)},
    )

    for table in model.tables:
        if table.is_hidden:
            continue

        table_node = LineageNode(
            name=table.name,
            node_type="table",
            metadata={
                "column_count": len(table.columns),
                "measure_count": len(table.measures),
            },
        )

        for report in reports:
            report_uses_table = False
            report_link = build_report_link(workspace_id, report.id, "") if workspace_id else None
            report_node = LineageNode(
                name=report.name,
                node_type="report",
                metadata={"id": report.id, **({
                    "workspace_id": workspace_id,
                    "report_link": report_link,
                } if workspace_id else {})},
            )

            for page in report.pages:
                page_uses_table = False
                page_link = build_report_link(workspace_id, report.id, page.name) if workspace_id else None
                page_node = LineageNode(
                    name=page.display_name,
                    node_type="page",
                    metadata={"name": page.name, **({
                        "report_link": page_link,
                    } if page_link else {})},
                )

                for visual in page.visuals:
                    visual_table_bindings = [
                        fb for fb in visual.field_bindings
                        if fb.table_name == table.name
                    ]

                    if visual_table_bindings:
                        visual_title = visual.title or visual.visual_type
                        v_link = build_visual_link(
                            workspace_id, report.id, page.name, visual.visual_id
                        ) if workspace_id and visual.visual_id else None
                        visual_node = LineageNode(
                            name=visual.visual_type,
                            node_type="visual",
                            metadata={
                                "title": visual_title,
                                **({
                                    "visual_id": visual.visual_id,
                                    "visual_link": v_link,
                                    "report_link": page_link,
                                } if visual.visual_id else {}),
                            },
                        )

                        for fb in visual_table_bindings:
                            field_node = LineageNode(
                                name=fb.field_name,
                                node_type=fb.field_type,
                                metadata={"table": fb.table_name, "field_type": fb.field_type},
                            )
                            visual_node.children.append(field_node)

                        page_node.children.append(visual_node)
                        page_uses_table = True

                if page_uses_table:
                    report_node.children.append(page_node)
                    report_uses_table = True

            if report_uses_table:
                table_node.children.append(report_node)

        if table_node.children:
            model_node.children.append(table_node)

    used_table_names = {child.name for child in model_node.children}
    for table in model.tables:
        if table.name not in used_table_names and not table.is_hidden:
            orphan_node = LineageNode(
                name=table.name,
                node_type="table",
                metadata={
                    "column_count": len(table.columns),
                    "measure_count": len(table.measures),
                    "orphan": True,
                },
            )
            model_node.children.append(orphan_node)

    return model_node


def get_impact_analysis(
    object_name: str,
    object_type: str,
    table_name: str,
    reports: list[ReportInfo],
    workspace_id: str = "",
) -> ImpactAnalysisResponse:
    used_in: list[ImpactItem] = []

    for report in reports:
        for page in report.pages:
            for visual in page.visuals:
                for fb in visual.field_bindings:
                    if (
                        fb.table_name == table_name
                        and fb.field_name == object_name
                        and fb.field_type == object_type
                    ):
                        v_link = build_visual_link(
                            workspace_id, report.id, page.name, visual.visual_id
                        ) if workspace_id and visual.visual_id else None
                        r_link = build_report_link(
                            workspace_id, report.id, page.name
                        ) if workspace_id else None
                        used_in.append(ImpactItem(
                            report_name=report.name,
                            page_name=page.display_name,
                            visual_type=visual.visual_type,
                            visual_title=visual.title,
                            visual_link=v_link,
                            report_link=r_link,
                        ))

    return ImpactAnalysisResponse(
        object_name=object_name, object_type=object_type,
        table_name=table_name, used_in=used_in, usage_count=len(used_in),
    )


def get_all_impact_analysis(
    model: SemanticModelInfo,
    reports: list[ReportInfo],
    workspace_id: str = "",
) -> list[ImpactAnalysisResponse]:
    results: list[ImpactAnalysisResponse] = []
    for table in model.tables:
        if table.is_hidden:
            continue
        for col in table.columns:
            if col.is_hidden:
                continue
            impact = get_impact_analysis(col.name, "column", table.name, reports, workspace_id)
            if impact.usage_count > 0:
                results.append(impact)
        for measure in table.measures:
            impact = get_impact_analysis(measure.name, "measure", table.name, reports, workspace_id)
            if impact.usage_count > 0:
                results.append(impact)
    results.sort(key=lambda x: x.usage_count, reverse=True)
    return results
