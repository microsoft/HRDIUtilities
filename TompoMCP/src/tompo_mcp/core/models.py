"""Pydantic data models for TOMPo — semantic models, reports, lineage."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Workspace ──────────────────────────────────────────────────────────────


class Workspace(BaseModel):
    id: str
    name: str
    type: Optional[str] = None
    state: Optional[str] = None


# ── Semantic Model (Dataset) ───────────────────────────────────────────────


class ColumnInfo(BaseModel):
    name: str
    data_type: str = "Unknown"
    is_hidden: bool = False
    expression: Optional[str] = None
    description: Optional[str] = None
    source_column: Optional[str] = None


class MeasureInfo(BaseModel):
    name: str
    expression: str = ""
    format_string: Optional[str] = None
    description: Optional[str] = None
    table_name: str = ""


class RelationshipInfo(BaseModel):
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    from_cardinality: str = "many"
    to_cardinality: str = "one"
    cross_filter: str = "oneDirection"
    is_active: bool = True


class RoleMember(BaseModel):
    member_name: str
    member_type: Optional[str] = None


class RoleInfo(BaseModel):
    name: str
    model_permission: str = "read"
    table_permissions: list[dict[str, str]] = Field(default_factory=list)
    members: list[RoleMember] = Field(default_factory=list)


class TableInfo(BaseModel):
    name: str
    is_hidden: bool = False
    description: Optional[str] = None
    source: Optional[str] = None
    columns: list[ColumnInfo] = Field(default_factory=list)
    measures: list[MeasureInfo] = Field(default_factory=list)


class SemanticModelInfo(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    tables: list[TableInfo] = Field(default_factory=list)
    relationships: list[RelationshipInfo] = Field(default_factory=list)
    roles: list[RoleInfo] = Field(default_factory=list)


# ── Report / Visual Lineage ───────────────────────────────────────────────


class VisualFieldBinding(BaseModel):
    table_name: str
    field_name: str
    field_type: str  # "column" or "measure"


class VisualInfo(BaseModel):
    visual_type: str
    title: Optional[str] = None
    visual_id: Optional[str] = None
    field_bindings: list[VisualFieldBinding] = Field(default_factory=list)
    filters: list[dict[str, Any]] = Field(default_factory=list)


class PageInfo(BaseModel):
    name: str
    display_name: str
    ordinal: int = 0
    visibility: Optional[str] = None
    visuals: list[VisualInfo] = Field(default_factory=list)


class ReportInfo(BaseModel):
    id: str
    name: str
    dataset_id: Optional[str] = None
    pages: list[PageInfo] = Field(default_factory=list)


# ── Lineage Tree ──────────────────────────────────────────────────────────


class LineageNode(BaseModel):
    name: str
    node_type: str  # model, table, report, page, visual, column, measure
    children: list[LineageNode] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LineageResponse(BaseModel):
    model: SemanticModelInfo
    reports: list[ReportInfo]
    lineage_tree: LineageNode


# ── Impact Analysis ───────────────────────────────────────────────────────


class ImpactItem(BaseModel):
    report_name: str
    page_name: str
    visual_type: str
    visual_title: Optional[str] = None
    visual_link: Optional[str] = None
    report_link: Optional[str] = None


class ImpactAnalysisResponse(BaseModel):
    object_name: str
    object_type: str  # "column" or "measure"
    table_name: str
    used_in: list[ImpactItem] = Field(default_factory=list)
    usage_count: int = 0
