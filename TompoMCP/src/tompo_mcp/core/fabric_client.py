"""Power BI and Fabric REST API client (standalone — no FastAPI dependency)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any, Optional

import httpx

from tompo_mcp.auth import TokenProvider

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 300.0
POLL_INTERVAL = 3
MAX_POLL_ATTEMPTS = 80

RESTRICTED_LABELS = {"confidential", "highly confidential", "restricted", "secret"}

PBI_BASE = "https://api.powerbi.com/v1.0/myorg"
FABRIC_BASE = "https://api.fabric.microsoft.com/v1"


class FabricClient:
    """Async client for Power BI and Fabric REST APIs."""

    def __init__(self, token_provider: TokenProvider) -> None:
        self._tp = token_provider
        self._pbi_base = PBI_BASE
        self._fabric_base = FABRIC_BASE
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create a shared httpx client (connection pooling)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _pbi_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._tp.get_powerbi_token()}",
            "Content-Type": "application/json",
        }

    def _fabric_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._tp.get_fabric_token()}",
            "Content-Type": "application/json",
        }

    # ── Workspace Operations ──────────────────────────────────────────

    async def list_workspaces(self) -> list[dict[str, Any]]:
        client = await self._get_client()
        resp = await client.get(
            f"{self._pbi_base}/groups",
            headers=self._pbi_headers(),
            params={"$top": 1000},
        )
        resp.raise_for_status()
        return resp.json().get("value", [])

    async def get_workspace_items(
        self, workspace_id: str
    ) -> dict[str, list[dict[str, Any]]]:
        client = await self._get_client()
        datasets_resp, reports_resp = await asyncio.gather(
            client.get(
                f"{self._pbi_base}/groups/{workspace_id}/datasets",
                headers=self._pbi_headers(),
            ),
            client.get(
                f"{self._pbi_base}/groups/{workspace_id}/reports",
                headers=self._pbi_headers(),
            ),
        )
        datasets_resp.raise_for_status()
        reports_resp.raise_for_status()
        return {
            "datasets": datasets_resp.json().get("value", []),
            "reports": reports_resp.json().get("value", []),
        }

    # ── Semantic Model Definition ─────────────────────────────────────

    async def get_semantic_model_definition(
        self, workspace_id: str, dataset_id: str
    ) -> Optional[dict[str, Any]]:
        async def _fetch_all_strategies():
            definition = await self._get_definition_fabric(
                workspace_id, "semanticModels", dataset_id
            )
            if definition:
                return definition

            logger.info("Fabric getDefinition failed, trying Admin Scanner API...")
            scanner_result = await self._scan_workspace_admin(workspace_id, dataset_id)
            if scanner_result:
                return scanner_result

            logger.info("Scanner API failed, trying DAX executeQueries...")
            dax_result = await self._get_metadata_via_dax(workspace_id, dataset_id)
            if dax_result:
                return dax_result

            return None

        result = await self._with_label_downgrade(
            workspace_id, "datasets", dataset_id, _fetch_all_strategies
        )

        if not result:
            logger.error(
                "All metadata extraction strategies failed for dataset %s",
                dataset_id,
            )
        return result

    async def _get_definition_fabric(
        self, workspace_id: str, item_type: str, item_id: str
    ) -> Optional[dict[str, Any]]:
        try:
            client = await self._get_client()
            url = f"{self._fabric_base}/workspaces/{workspace_id}/{item_type}/{item_id}/getDefinition"
            resp = await client.post(url, headers=self._fabric_headers())

            if resp.status_code == 200:
                return self._decode_definition_parts(resp.json())
            if resp.status_code == 202:
                return await self._poll_long_running_operation(client, resp)

            logger.warning(
                "getDefinition returned %d for %s/%s",
                resp.status_code, item_type, item_id,
            )
            return None
        except Exception as exc:
            logger.warning("Fabric getDefinition failed: %s", exc)
            return None

    async def _poll_long_running_operation(
        self, client: httpx.AsyncClient, initial_resp: httpx.Response
    ) -> Optional[dict[str, Any]]:
        location = initial_resp.headers.get("Location")
        retry_after = int(initial_resp.headers.get("Retry-After", str(POLL_INTERVAL)))

        if not location:
            logger.warning("No Location header in 202 response")
            return None

        for _attempt in range(MAX_POLL_ATTEMPTS):
            await asyncio.sleep(retry_after)
            poll_resp = await client.get(location, headers=self._fabric_headers())

            if poll_resp.status_code == 200:
                body = poll_resp.json()
                if "definition" in body:
                    return self._decode_definition_parts(body)
                result_location = poll_resp.headers.get("Location")
                if result_location:
                    result_resp = await client.get(
                        result_location, headers=self._fabric_headers()
                    )
                    if result_resp.status_code == 200:
                        return self._decode_definition_parts(result_resp.json())
                return body

            if poll_resp.status_code == 202:
                retry_after = int(
                    poll_resp.headers.get("Retry-After", str(POLL_INTERVAL))
                )
                continue

            logger.warning("Poll returned unexpected status %d", poll_resp.status_code)
            return None

        logger.error("Long-running operation timed out")
        return None

    def _decode_definition_parts(self, response_body: dict[str, Any]) -> dict[str, Any]:
        definition = response_body.get("definition", {})
        parts = definition.get("parts", [])
        decoded: dict[str, Any] = {"_format": definition.get("format", "unknown")}

        for part in parts:
            path = part.get("path", "")
            payload = part.get("payload", "")
            payload_type = part.get("payloadType", "")

            if payload_type == "InlineBase64" and payload:
                try:
                    decoded_bytes = base64.b64decode(payload)
                    content = decoded_bytes.decode("utf-8")
                    try:
                        decoded[path] = json.loads(content)
                    except json.JSONDecodeError:
                        decoded[path] = content
                except Exception as exc:
                    logger.warning("Failed to decode part %s: %s", path, exc)
                    decoded[path] = payload
            else:
                decoded[path] = payload

        return decoded

    # ── Fallback: Admin Scanner API ───────────────────────────────────

    async def _scan_workspace_admin(
        self, workspace_id: str, dataset_id: str
    ) -> Optional[dict[str, Any]]:
        try:
            client = await self._get_client()
            scan_resp = await client.post(
                f"{self._pbi_base}/admin/workspaces/getInfo",
                headers=self._pbi_headers(),
                params={"datasetSchema": "true", "datasetExpressions": "true"},
                json={"workspaces": [workspace_id]},
            )

            if scan_resp.status_code != 202:
                logger.warning("Scanner API trigger returned %d", scan_resp.status_code)
                return None

            scan_id = scan_resp.json().get("id")
            if not scan_id:
                return None

            for _ in range(MAX_POLL_ATTEMPTS):
                await asyncio.sleep(POLL_INTERVAL)
                status_resp = await client.get(
                    f"{self._pbi_base}/admin/workspaces/scanStatus/{scan_id}",
                    headers=self._pbi_headers(),
                )
                status = status_resp.json()
                if status.get("status") == "Succeeded":
                    break
            else:
                logger.error("Scanner API timed out")
                return None

            result_resp = await client.get(
                f"{self._pbi_base}/admin/workspaces/scanResult/{scan_id}",
                headers=self._pbi_headers(),
            )
            result_resp.raise_for_status()
            scan_result = result_resp.json()

            for ws in scan_result.get("workspaces", []):
                for ds in ws.get("datasets", []):
                    if ds.get("id") == dataset_id:
                        return {"_source": "scanner", "dataset": ds}
            return None
        except Exception as exc:
            logger.warning("Admin Scanner API failed: %s", exc)
            return None

    # ── Fallback: DAX executeQueries ──────────────────────────────────

    async def _get_metadata_via_dax(
        self, workspace_id: str, dataset_id: str
    ) -> Optional[dict[str, Any]]:
        dax_queries = {
            "tables": "EVALUATE SELECTCOLUMNS(INFO.TABLES(), \"ID\", [ID], \"Name\", [Name], \"IsHidden\", [IsHidden], \"Description\", [Description])",
            "columns": "EVALUATE SELECTCOLUMNS(INFO.COLUMNS(), \"ID\", [ID], \"TableID\", [TableID], \"ExplicitName\", [ExplicitName], \"InferredName\", [InferredName], \"ExplicitDataType\", [ExplicitDataType], \"IsHidden\", [IsHidden], \"Expression\", [Expression], \"Description\", [Description])",
            "measures": "EVALUATE SELECTCOLUMNS(INFO.MEASURES(), \"TableID\", [TableID], \"Name\", [Name], \"Expression\", [Expression], \"FormatString\", [FormatString], \"Description\", [Description])",
            "relationships": "EVALUATE SELECTCOLUMNS(INFO.RELATIONSHIPS(), \"ID\", [ID], \"FromTableID\", [FromTableID], \"FromColumnID\", [FromColumnID], \"ToTableID\", [ToTableID], \"ToColumnID\", [ToColumnID], \"FromCardinality\", [FromCardinality], \"ToCardinality\", [ToCardinality], \"CrossFilteringBehavior\", [CrossFilteringBehavior], \"IsActive\", [IsActive])",
            "roles": "EVALUATE SELECTCOLUMNS(INFO.ROLES(), \"ID\", [ID], \"Name\", [Name], \"ModelPermission\", [ModelPermission], \"Description\", [Description])",
        }

        try:
            results: dict[str, Any] = {"_source": "dax"}
            client = await self._get_client()
            for key, dax in dax_queries.items():
                resp = await client.post(
                    f"{self._pbi_base}/groups/{workspace_id}/datasets/{dataset_id}/executeQueries",
                    headers=self._pbi_headers(),
                    json={
                        "queries": [{"query": dax}],
                        "serializerSettings": {"includeNulls": True},
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    rows = (
                        data.get("results", [{}])[0]
                        .get("tables", [{}])[0]
                        .get("rows", [])
                    )
                    results[key] = rows
                else:
                    logger.warning("DAX query for '%s' returned %d", key, resp.status_code)
                    results[key] = []

            return results if any(results.get(k) for k in dax_queries) else None
        except Exception as exc:
            logger.warning("DAX executeQueries failed: %s", exc)
            return None

    # ── Report Definition ─────────────────────────────────────────────

    async def get_report_definition(
        self, workspace_id: str, report_id: str
    ) -> Optional[dict[str, Any]]:
        async def _fetch_report():
            definition = await self._get_definition_fabric(
                workspace_id, "reports", report_id
            )
            if definition:
                return definition

            logger.info("Report getDefinition failed, falling back to Pages API...")
            pages = await self._get_report_pages_fallback(workspace_id, report_id)
            if pages:
                return {"_source": "pages_api", "pages": pages}
            return None

        return await self._with_label_downgrade(
            workspace_id, "reports", report_id, _fetch_report
        )

    async def _get_report_pages_fallback(
        self, workspace_id: str, report_id: str
    ) -> Optional[list[dict[str, Any]]]:
        try:
            client = await self._get_client()
            resp = await client.get(
                f"{self._pbi_base}/groups/{workspace_id}/reports/{report_id}/pages",
                headers=self._pbi_headers(),
            )
            if resp.status_code == 200:
                return resp.json().get("value", [])
            return None
        except Exception as exc:
            logger.warning("Pages API fallback failed: %s", exc)
            return None

    # ── Sensitivity Label Management ────────────────────────────────────

    async def _get_artifact_sensitivity_label(
        self, workspace_id: str, artifact_type: str, artifact_id: str
    ) -> Optional[dict[str, Any]]:
        try:
            client = await self._get_client()
            if artifact_type == "datasets":
                url = f"{self._pbi_base}/admin/datasets/{artifact_id}"
            elif artifact_type == "reports":
                url = f"{self._pbi_base}/admin/reports/{artifact_id}"
            else:
                return None

            resp = await client.get(url, headers=self._pbi_headers())
            if resp.status_code == 200:
                data = resp.json()
                label = data.get("sensitivityLabel")
                if label:
                    return {
                        "labelId": label.get("labelId"),
                        "labelName": label.get("labelId"),
                    }
                return None
            return None
        except Exception as exc:
            logger.warning("Failed to get sensitivity label: %s", exc)
            return None

    async def _get_general_label_id(self) -> Optional[str]:
        if hasattr(self, "_general_label_id_cache"):
            return self._general_label_id_cache

        try:
            client = await self._get_client()
            headers = {
                "Authorization": f"Bearer {self._tp.get_graph_token()}",
                "Content-Type": "application/json",
            }
            resp = await client.get(
                "https://graph.microsoft.com/v1.0/informationProtection/policy/labels",
                headers=headers,
            )
            if resp.status_code == 200:
                labels = resp.json().get("value", [])
                for lbl in labels:
                    name = (lbl.get("name") or "").lower()
                    if name in ("general", "public"):
                        self._general_label_id_cache = lbl["id"]
                        return self._general_label_id_cache
        except Exception as exc:
            logger.warning("Failed to discover General label ID: %s", exc)

        self._general_label_id_cache = None
        return None

    async def _set_sensitivity_label(
        self, artifact_type: str, artifact_id: str, label_id: str
    ) -> bool:
        try:
            field_map = {"datasets": "datasets", "reports": "reports"}
            field = field_map.get(artifact_type)
            if not field:
                return False

            payload = {
                "artifacts": {field: [{"id": artifact_id}]},
                "labelId": label_id,
                "assignmentMethod": "Standard",
            }
            client = await self._get_client()
            resp = await client.post(
                f"{self._pbi_base}/admin/informationprotection/setLabels",
                headers=self._pbi_headers(),
                json=payload,
            )
            if resp.status_code == 200:
                result = resp.json()
                items = result.get(field, [])
                if items and items[0].get("status") == "Succeeded":
                    return True
            return False
        except Exception as exc:
            logger.warning("Failed to set sensitivity label: %s", exc)
            return False

    async def _with_label_downgrade(
        self, workspace_id: str, artifact_type: str, artifact_id: str, fetch_fn
    ) -> Optional[dict[str, Any]]:
        result = await fetch_fn()
        if result is not None:
            return result

        logger.info("Initial fetch failed for %s/%s, checking sensitivity label...", artifact_type, artifact_id)

        original_label = await self._get_artifact_sensitivity_label(
            workspace_id, artifact_type, artifact_id
        )

        if not original_label or not original_label.get("labelId"):
            return None

        original_label_id = original_label["labelId"]
        general_label_id = await self._get_general_label_id()

        if not general_label_id or original_label_id == general_label_id:
            return None

        logger.info("Temporarily setting %s/%s label to General for parsing...", artifact_type, artifact_id)
        downgrade_ok = await self._set_sensitivity_label(artifact_type, artifact_id, general_label_id)

        if not downgrade_ok:
            return None

        await asyncio.sleep(2)

        try:
            result = await fetch_fn()
            return result
        finally:
            logger.info("Restoring original label %s on %s/%s...", original_label_id, artifact_type, artifact_id)
            restore_ok = await self._set_sensitivity_label(artifact_type, artifact_id, original_label_id)
            if not restore_ok:
                logger.error(
                    "CRITICAL: Failed to restore original label %s on %s/%s!",
                    original_label_id, artifact_type, artifact_id,
                )

    # ── Reports for Dataset ───────────────────────────────────────────

    async def get_reports_for_dataset(
        self, workspace_id: str, dataset_id: str
    ) -> list[dict[str, Any]]:
        items = await self.get_workspace_items(workspace_id)
        return [r for r in items.get("reports", []) if r.get("datasetId") == dataset_id]
