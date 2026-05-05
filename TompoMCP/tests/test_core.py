"""Tests for TOMPo MCP core logic (parser, lineage builder, link builder)."""

from tompo_mcp.core.models import (
    ColumnInfo, LineageNode, MeasureInfo, PageInfo, ReportInfo,
    SemanticModelInfo, TableInfo, VisualFieldBinding, VisualInfo,
)
from tompo_mcp.core.lineage import build_lineage, get_impact_analysis, get_all_impact_analysis
from tompo_mcp.core.links import build_report_link, build_visual_link, set_pbi_web_url
from tompo_mcp.core.parser import parse_semantic_model, parse_report_definition


# ── Test data ────────────────────────────────────────────────────────

def _make_model() -> SemanticModelInfo:
    return SemanticModelInfo(
        id="ds-001",
        name="Sales Model",
        tables=[
            TableInfo(
                name="DimCustomer",
                columns=[
                    ColumnInfo(name="CustomerID", data_type="Int64"),
                    ColumnInfo(name="Name", data_type="String"),
                    ColumnInfo(name="Region", data_type="String"),
                ],
                measures=[
                    MeasureInfo(name="CustomerCount", expression="COUNTROWS(DimCustomer)", table_name="DimCustomer"),
                ],
            ),
            TableInfo(
                name="FactSales",
                columns=[
                    ColumnInfo(name="SalesID", data_type="Int64"),
                    ColumnInfo(name="Amount", data_type="Decimal"),
                ],
                measures=[
                    MeasureInfo(name="TotalRevenue", expression="SUM(FactSales[Amount])", table_name="FactSales"),
                ],
            ),
            TableInfo(name="HiddenTable", is_hidden=True, columns=[ColumnInfo(name="X", data_type="String")]),
        ],
    )


def _make_reports() -> list[ReportInfo]:
    return [
        ReportInfo(
            id="rpt-001",
            name="Sales Dashboard",
            dataset_id="ds-001",
            pages=[
                PageInfo(
                    name="ReportSection1",
                    display_name="Overview",
                    ordinal=0,
                    visuals=[
                        VisualInfo(
                            visual_type="clusteredBarChart",
                            title="Revenue by Region",
                            visual_id="v1",
                            field_bindings=[
                                VisualFieldBinding(table_name="DimCustomer", field_name="Region", field_type="column"),
                                VisualFieldBinding(table_name="FactSales", field_name="TotalRevenue", field_type="measure"),
                            ],
                        ),
                        VisualInfo(
                            visual_type="card",
                            title="Customer Count",
                            visual_id="v2",
                            field_bindings=[
                                VisualFieldBinding(table_name="DimCustomer", field_name="CustomerCount", field_type="measure"),
                            ],
                        ),
                    ],
                ),
                PageInfo(
                    name="ReportSection2",
                    display_name="Details",
                    ordinal=1,
                    visuals=[
                        VisualInfo(
                            visual_type="table",
                            title="Customer Grid",
                            visual_id="v3",
                            field_bindings=[
                                VisualFieldBinding(table_name="DimCustomer", field_name="Name", field_type="column"),
                                VisualFieldBinding(table_name="DimCustomer", field_name="Region", field_type="column"),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ]


# ── Lineage builder tests ────────────────────────────────────────────

def test_build_lineage():
    model = _make_model()
    reports = _make_reports()
    result = build_lineage(model, reports, workspace_id="ws-001")

    assert result.model.name == "Sales Model"
    assert len(result.reports) == 1

    tree = result.lineage_tree
    assert tree.node_type == "model"
    assert tree.name == "Sales Model"

    # DimCustomer and FactSales should be children (HiddenTable excluded)
    table_names = [c.name for c in tree.children]
    assert "DimCustomer" in table_names
    assert "FactSales" in table_names
    assert "HiddenTable" not in table_names


def test_lineage_tree_structure():
    model = _make_model()
    reports = _make_reports()
    result = build_lineage(model, reports, workspace_id="ws-001")
    tree = result.lineage_tree

    # Find DimCustomer
    dim_cust = next(c for c in tree.children if c.name == "DimCustomer")
    assert dim_cust.node_type == "table"
    assert dim_cust.metadata["column_count"] == 3
    assert dim_cust.metadata["measure_count"] == 1

    # DimCustomer → Sales Dashboard report
    assert len(dim_cust.children) == 1
    report_node = dim_cust.children[0]
    assert report_node.name == "Sales Dashboard"
    assert report_node.node_type == "report"

    # Report → pages
    assert len(report_node.children) == 2  # Overview + Details
    overview = next(p for p in report_node.children if p.name == "Overview")
    assert overview.node_type == "page"

    # Overview → visuals using DimCustomer
    visual_types = [v.name for v in overview.children]
    assert "clusteredBarChart" in visual_types
    assert "card" in visual_types


def test_impact_analysis():
    model = _make_model()
    reports = _make_reports()

    result = get_impact_analysis("Region", "column", "DimCustomer", reports, "ws-001")
    assert result.usage_count == 2  # In Revenue by Region + Customer Grid
    assert result.object_name == "Region"

    result2 = get_impact_analysis("CustomerCount", "measure", "DimCustomer", reports, "ws-001")
    assert result2.usage_count == 1  # Only in Customer Count card


def test_all_impact_analysis():
    model = _make_model()
    reports = _make_reports()
    results = get_all_impact_analysis(model, reports, "ws-001")

    # Should have entries for Region (2), Name (1), CustomerCount (1), TotalRevenue (1)
    assert len(results) >= 4
    # Sorted by usage_count desc
    assert results[0].usage_count >= results[-1].usage_count


# ── Link builder tests ───────────────────────────────────────────────

def test_report_link():
    set_pbi_web_url("https://app.powerbi.com")
    link = build_report_link("ws-001", "rpt-001", "ReportSection1")
    assert link == "https://app.powerbi.com/groups/ws-001/reports/rpt-001/ReportSection1"


def test_visual_link():
    set_pbi_web_url("https://app.powerbi.com")
    link = build_visual_link("ws-001", "rpt-001", "ReportSection1", "v1")
    assert link == "https://app.powerbi.com/groups/ws-001/reports/rpt-001/ReportSection1?visual=v1"


def test_link_none_on_missing():
    assert build_report_link("", "rpt-001") is None
    assert build_visual_link("ws-001", "rpt-001", "page", None) is None


# ── Parser tests ─────────────────────────────────────────────────────

def test_parse_bim_model():
    raw = {
        "model.bim": {
            "model": {
                "tables": [
                    {
                        "name": "Products",
                        "columns": [
                            {"name": "ProductID", "dataType": "int64"},
                            {"name": "ProductName", "dataType": "string"},
                        ],
                        "measures": [
                            {"name": "ProductCount", "expression": "COUNTROWS(Products)"},
                        ],
                    }
                ],
                "relationships": [],
            }
        }
    }
    model = parse_semantic_model(raw, "ds-test", "Test Model")
    assert model.name == "Test Model"
    assert len(model.tables) == 1
    assert model.tables[0].name == "Products"
    assert len(model.tables[0].columns) == 2
    assert len(model.tables[0].measures) == 1


def test_parse_dax_model():
    raw = {
        "_source": "dax",
        "tables": [
            {"[ID]": 1, "[Name]": "Sales", "[IsHidden]": False, "[Description]": None},
        ],
        "columns": [
            {"[TableID]": 1, "[ExplicitName]": "Amount", "[InferredName]": None, "[ExplicitDataType]": "Decimal", "[IsHidden]": False, "[Expression]": None, "[Description]": None},
        ],
        "measures": [
            {"[TableID]": 1, "[Name]": "Total", "[Expression]": "SUM(Sales[Amount])", "[FormatString]": "#,0", "[Description]": None},
        ],
        "relationships": [],
        "roles": [],
    }
    model = parse_semantic_model(raw, "ds-dax", "DAX Model")
    assert model.name == "DAX Model"
    assert len(model.tables) == 1
    assert model.tables[0].columns[0].name == "Amount"
    assert model.tables[0].measures[0].name == "Total"


def test_parse_pbir_report():
    raw = {
        "definition/pages/page1/page.json": {
            "displayName": "Overview",
            "ordinal": 0,
        },
        "definition/pages/page1/visuals/vis1/visual.json": {
            "visual": {
                "visualType": "barChart",
                "prototypeQuery": {
                    "Select": [
                        {"Column": {"Expression": {"SourceRef": {"Entity": "Sales"}}, "Property": "Region"}},
                        {"Measure": {"Expression": {"SourceRef": {"Entity": "Sales"}}, "Property": "Total"}},
                    ]
                },
            }
        },
    }
    report = parse_report_definition(raw, "rpt-test", "Test Report", "ds-test")
    assert report.name == "Test Report"
    assert len(report.pages) == 1
    assert report.pages[0].display_name == "Overview"
    assert len(report.pages[0].visuals) == 1
    fb = report.pages[0].visuals[0].field_bindings
    assert len(fb) == 2
    assert fb[0].table_name == "Sales"
    assert fb[0].field_name == "Region"
    assert fb[0].field_type == "column"
    assert fb[1].field_type == "measure"


# ── Run tests ────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_build_lineage()
    test_lineage_tree_structure()
    test_impact_analysis()
    test_all_impact_analysis()
    test_report_link()
    test_visual_link()
    test_link_none_on_missing()
    test_parse_bim_model()
    test_parse_dax_model()
    test_parse_pbir_report()
    print("All tests passed!")
