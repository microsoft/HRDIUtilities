"""Power BI deep link builder."""

from __future__ import annotations

from urllib.parse import quote

# Default Power BI web portal URL
DEFAULT_PBI_WEB_URL = "https://app.powerbi.com"

_pbi_web_url: str = DEFAULT_PBI_WEB_URL


def set_pbi_web_url(url: str) -> None:
    global _pbi_web_url
    _pbi_web_url = url.rstrip("/")


def build_report_link(
    workspace_id: str,
    report_id: str,
    page_name: str = "",
) -> str | None:
    if not workspace_id or not report_id:
        return None
    url = f"{_pbi_web_url}/groups/{workspace_id}/reports/{report_id}"
    if page_name:
        url += f"/{quote(page_name, safe='')}"
    return url


def build_visual_link(
    workspace_id: str,
    report_id: str,
    page_name: str,
    visual_id: str | None,
) -> str | None:
    if not workspace_id or not report_id or not visual_id:
        return None
    url = (
        f"{_pbi_web_url}/groups/{workspace_id}/reports/{report_id}"
        f"/{quote(page_name, safe='')}"
        f"?visual={quote(visual_id, safe='')}"
    )
    return url
