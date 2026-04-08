#!/usr/bin/env python3
"""
Fabric Infrastructure Deployment
=================================

Deploys core Fabric infrastructure components in dependency order:
  1. Lakehouse  (foundation for shortcuts and notebooks)
  2. Connection (required for shortcuts)
  3. Shortcuts  (depend on lakehouse + connection)
  4. Spark Pool (independent)
  5. OneLake Folders (depend on lakehouse)
  6. Workspace Access (SPN / identity RBAC)

All parameters are read from fabric_config.json.

Usage:
    python fabric_infra_deploy.py
    python fabric_infra_deploy.py --verbose_logging
    python fabric_infra_deploy.py --minimal_logging
"""

import os
import json
import subprocess
import argparse
from pathlib import Path
from typing import Tuple
from shared_logger import SharedLogger


class FabricInfraDeployment:
    """Config-driven deployment of Fabric infrastructure artifacts."""

    def __init__(self, config_path: str = None, verbose_logging: bool = False,
                 minimal_logging: bool = False):
        self.verbose_logging = verbose_logging
        self.minimal_logging = minimal_logging

        # Resolve paths relative to repo root (FabricCLI/)
        script_dir = Path(__file__).parent
        self.workspace_root = script_dir.parent
        self.config_path = Path(config_path) if config_path else self.workspace_root / "Config" / "fabric_config.json"

        # Load workspace name
        self.target_workspace = self._clean_workspace_name(
            self._get_config_value("fabricWorkspaceName")
        )

        # Logger
        self.logger = SharedLogger("fabric_infra_deploy.py", str(self.workspace_root), minimal_logging)

        # Deployment statistics
        self.stats = {
            "lakehouse": {"created": 0, "already_exists": 0, "failed": 0},
            "connection": {"created": 0, "already_exists": 0, "failed": 0},
            "shortcuts": {"created": 0, "already_exists": 0, "failed": 0},
            "spark_pool": {"created": 0, "already_exists": 0, "failed": 0},
            "folders": {"created": 0, "already_exists": 0, "failed": 0},
            "workspace_access": {"created": 0, "already_exists": 0, "failed": 0},
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _clean_workspace_name(name: str) -> str:
        for prefix in ("/workspaces/",):
            if name.startswith(prefix):
                name = name[len(prefix):]
        return name.rstrip("/").replace(".Workspace", "")

    def _get_config_value(self, key: str, required: bool = True):
        """Read a parameter value from fabric_config.json."""
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        val = data.get("parameters", {}).get(key, {}).get("value")
        if required and val is None:
            raise ValueError(f"'{key}' not found in {self.config_path}")
        return val

    def _is_placeholder(self, value) -> bool:
        """Check if a config value is still a ##placeholder## or empty."""
        if value is None:
            return True
        s = str(value).strip()
        return s == "" or (s.startswith("##") and s.endswith("##"))

    def _set_config_value(self, key: str, value):
        """Write a single parameter value back to fabric_config.json."""
        with open(self.config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        cfg.setdefault("parameters", {})[key] = {"value": value}
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

    def _run(self, cmd: str, capture: bool = False) -> Tuple[bool, str, str]:
        """Execute a shell command and return (success, stdout, stderr)."""
        self.logger.write_log(f"[DEBUG] {cmd}", "DEBUG")
        actual_capture = capture or self.minimal_logging
        try:
            r = subprocess.run(cmd, shell=True, capture_output=actual_capture,
                               text=True if actual_capture else None,
                               timeout=300, cwd=None)
            out = r.stdout.strip() if actual_capture and r.stdout else ""
            err = r.stderr.strip() if actual_capture and r.stderr else ""
            return r.returncode == 0, out, err
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as exc:
            return False, "", str(exc)

    def _exists(self, path: str) -> bool:
        ok, out, _ = self._run(f'fab exists "{path}"', capture=True)
        return ok and "true" in out.lower()

    # ------------------------------------------------------------------
    # 0. Auto-resolve workspace and lakehouse config
    # ------------------------------------------------------------------
    def resolve_config(self) -> bool:
        """Derive workspace ID and lakehouse details so users only need to
        provide fabricWorkspaceName (and optionally fabricLakehouseName)."""
        self.logger.write_log("Resolving configuration from workspace...", "INFO")

        ws_path = f"{self.target_workspace}.Workspace"

        # --- Workspace ID ---
        ws_id = self._get_config_value("fabricWorkspaceId", required=False)
        if self._is_placeholder(ws_id):
            ok, resolved_id, _ = self._run(f'fab get "{ws_path}" -q id', capture=True)
            if ok and resolved_id:
                self._set_config_value("fabricWorkspaceId", resolved_id)
                self.logger.write_log(f"Resolved fabricWorkspaceId: {resolved_id}", "SUCCESS")
            else:
                self.logger.write_log("Could not resolve fabricWorkspaceId — verify workspace name.", "ERROR")
                return False
        else:
            self.logger.write_log(f"fabricWorkspaceId already set: {ws_id}", "INFO")

        # --- Lakehouse name ---
        lh_name = self._get_config_value("fabricLakehouseName", required=False)
        if self._is_placeholder(lh_name):
            tenant = self._get_config_value("tenantName", required=False) or "fabric"
            env = self._get_config_value("environmentName", required=False) or "dev"
            lh_name = f"{tenant.lower()}_lakehouse_{env.lower()}"
            self._set_config_value("fabricLakehouseName", lh_name)
            self.logger.write_log(f"Generated default lakehouse name: {lh_name}", "INFO")

        self.logger.write_log("Config resolution complete.", "SUCCESS")
        return True

    # ------------------------------------------------------------------
    # 1. Lakehouse
    # ------------------------------------------------------------------
    def create_lakehouse(self) -> bool:
        name = self._get_config_value("fabricLakehouseName", required=False)
        if not name:
            self.logger.write_log("No lakehouse name in config — skipping.", "WARNING")
            return True

        target = f"{self.target_workspace}.Workspace/{name}.Lakehouse"
        if self._exists(target):
            self.logger.write_log(f"Lakehouse '{name}' already exists.", "WARNING")
            self._update_lakehouse_config(name)
            self.stats["lakehouse"]["already_exists"] += 1
            return True

        cmd = f'fab create "{target}" -P enableschemas=true'
        ok, _, _ = self._run(cmd)
        if ok:
            self.logger.write_log(f"Lakehouse '{name}' created.", "SUCCESS")
            self.logger.log_to_csv(action="Infra Deploy", resource_name=name,
                                   resource_type="Lakehouse", status="created", success="successful")
            self._update_lakehouse_config(name)
            self.stats["lakehouse"]["created"] += 1
        else:
            self.logger.write_log(f"Failed to create lakehouse '{name}'.", "ERROR")
            self.logger.log_to_csv(action="Infra Deploy", resource_name=name,
                                   resource_type="Lakehouse", status="failed", success="failed",
                                   error_reason="Lakehouse creation failed")
            self.stats["lakehouse"]["failed"] += 1
        return ok

    def _update_lakehouse_config(self, name: str):
        """Retrieve lakehouse ID and connection string, then save them to config."""
        base = f"{self.target_workspace}.Workspace/{name}.Lakehouse"

        ok_id, lh_id, _ = self._run(f'fab get "{base}" -q id', capture=True)
        ok_cs, conn_str, _ = self._run(
            f'fab get "{base}" -q "properties.sqlEndpointProperties.connectionString"',
            capture=True,
        )

        with open(self.config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        p = cfg.setdefault("parameters", {})
        p["fabricLakehouseId"] = {"value": lh_id if ok_id else ""}
        p["lakehouseConnString"] = {"value": conn_str if ok_cs and conn_str else "##lakehouseConnString##"}
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

        if ok_id:
            self.logger.write_log(f"Lakehouse ID: {lh_id}", "SUCCESS")
        if ok_cs and conn_str:
            self.logger.write_log(f"Connection string updated.", "SUCCESS")

    # ------------------------------------------------------------------
    # 2. Connection
    # ------------------------------------------------------------------
    def create_connection(self) -> bool:
        cc = self._get_config_value("connectionConfiguration", required=False)
        if not cc or not cc.get("connectionName"):
            self.logger.write_log("No connection config — skipping.", "WARNING")
            return True

        storage = self._get_config_value("storageAccountName", required=False)
        if not storage or self._is_placeholder(storage) or str(storage).strip() == "":
            self.logger.write_log("No storage account configured — skipping connection.", "WARNING")
            return True

        tenant = self._get_config_value("tenantName", required=False) or ""
        env = self._get_config_value("environmentName", required=False) or ""

        base = cc["connectionName"]
        conn_name = f"{tenant}_{base}_{env}" if tenant and env else base
        display = f"{tenant}_{cc.get('displayName', base)}_{env}" if tenant and env else cc.get("displayName", base)

        path = f".connections/{conn_name}.Connection"
        if self._exists(path):
            self.logger.write_log(f"Connection '{conn_name}' already exists.", "WARNING")
            self.stats["connection"]["already_exists"] += 1
            return True

        cd = cc.get("connectionDetails", {})
        params = cd.get("parameters", {})
        server = f"{storage}.{params.get('serverSuffix', 'dfs.core.windows.net')}"
        cp = params.get("containerPath", "")
        final_path = f"/{cp}" if cp else params.get("path", "/")

        cmd = (
            f'fab create "{path}" -P '
            f'allowConnectionUsageInGateway={str(cc.get("allowConnectionUsageInGateway", False)).lower()},'
            f'displayName="{display}",'
            f'connectivityType={cc.get("connectivityType")},'
            f'connectionDetails.type={cd.get("type")},'
            f'connectionDetails.creationMethod={cd.get("creationMethod")},'
            f'connectionDetails.parameters.server="{server}",'
            f'connectionDetails.parameters.path="{final_path}",'
            f'privacyLevel={cc.get("privacyLevel")},'
            f'credentialDetails.type={cc.get("credentialDetails", {}).get("type")}'
        )

        ok, _, _ = self._run(cmd)
        status = "created" if ok else "failed"
        self.logger.write_log(f"Connection '{conn_name}' {status}.",
                              "SUCCESS" if ok else "ERROR")
        self.logger.log_to_csv(action="Infra Deploy", resource_name=conn_name,
                               resource_type="Connection", status=status,
                               success="successful" if ok else "failed")
        if ok:
            self.stats["connection"]["created"] += 1
        else:
            self.stats["connection"]["failed"] += 1
        return True  # non-fatal

    # ------------------------------------------------------------------
    # 3. Shortcuts
    # ------------------------------------------------------------------
    def create_shortcuts(self) -> bool:
        sc = self._get_config_value("shortcutConfiguration", required=False)
        if not sc or not sc.get("shortcuts"):
            self.logger.write_log("No shortcut config — skipping.", "WARNING")
            return True

        storage = self._get_config_value("storageAccountName", required=False)
        if not storage or self._is_placeholder(storage) or str(storage).strip() == "":
            self.logger.write_log("No storage account configured — skipping shortcuts.", "WARNING")
            return True

        lh = self._get_config_value("fabricLakehouseName", required=False)
        cc = self._get_config_value("connectionConfiguration", required=False)
        if not all([lh, cc]):
            self.logger.write_log("Missing lakehouse/connection config for shortcuts — skipping.", "WARNING")
            return True

        tenant = self._get_config_value("tenantName", required=False) or ""
        env = self._get_config_value("environmentName", required=False) or ""
        base = cc.get("connectionName", "")
        conn_name = f"{tenant}_{base}_{env}" if tenant and env else base

        # Get connection ID (direct subprocess call — matching working version)
        get_id_command = f'fab get ".connections/{conn_name}.Connection" -q id'
        self.logger.write_log(f"[DEBUG] {get_id_command}", "DEBUG")
        try:
            result = subprocess.run(
                get_id_command, shell=True, capture_output=True,
                timeout=60, text=True, cwd=None,
            )
            conn_id = result.stdout.strip() if result.returncode == 0 and result.stdout else ""
        except Exception:
            conn_id = ""

        if not conn_id:
            self.logger.write_log(f"Could not retrieve connection ID for '{conn_name}'.", "ERROR")
            return False
        self.logger.write_log(f"Connection ID: {conn_id}", "SUCCESS")

        shortcuts = sc["shortcuts"]
        self.logger.write_log(f"Creating {len(shortcuts)} shortcut(s)...", "INFO")
        ok_count = 0

        for idx, sc_def in enumerate(shortcuts, 1):
            name = sc_def["name"]
            container = sc_def["containerName"]
            sc_path = f"{self.target_workspace}.Workspace/{lh}.Lakehouse/Files/{name}.Shortcut"

            # Check if shortcut already exists (direct subprocess — matching working version)
            exists_command = f'fab exists "{sc_path}"'
            self.logger.write_log(f"[DEBUG] {exists_command}", "DEBUG")
            shortcut_exists = False
            try:
                result = subprocess.run(
                    exists_command, shell=True, capture_output=True,
                    timeout=60, text=True, cwd=None,
                )
                if result.returncode == 0:
                    exists_output = result.stdout.strip().lower() if result.stdout else ""
                    shortcut_exists = "true" in exists_output
            except Exception:
                shortcut_exists = False

            if shortcut_exists:
                self.logger.write_log(f"Shortcut '{name}' already exists.", "WARNING")
                self.stats["shortcuts"]["already_exists"] += 1
                ok_count += 1
                continue

            # Build JSON payload (exact format from working command)
            adls_location = f"https://{storage}.dfs.core.windows.net"
            container_subpath = f"/{container}"
            shortcut_json = {
                "location": adls_location,
                "subpath": container_subpath,
                "connectionId": conn_id
            }

            # Convert JSON to string with escaped quotes for the inner -i argument
            json_str = json.dumps(shortcut_json)
            json_payload = json_str.replace('"', '\\"')

            # Build command using PowerShell single quotes (exact working syntax)
            # cmd /c 'fab ln "path" --type adlsGen2 -f -i "{\"...\": \"...\"}"'
            create_command = f"cmd /c 'fab ln \"{sc_path}\" --type adlsGen2 -f -i \"{json_payload}\"'"

            self.logger.write_log(f"[{idx}/{len(shortcuts)}] Creating shortcut '{name}' -> /{container}...", "INFO")
            self.logger.write_log(f"[DEBUG] {create_command}", "DEBUG")

            # Execute via PowerShell so single quotes are interpreted correctly
            actual_capture = self.minimal_logging
            try:
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", create_command],
                    capture_output=actual_capture, timeout=300, cwd=None,
                    text=True if actual_capture else None,
                )
                ok = r.returncode == 0
            except Exception as e:
                ok = False
                self.logger.write_log(f"  Exception: {str(e)}", "ERROR")

            self.logger.write_log(f"Shortcut '{name}' {'created' if ok else 'FAILED'}.",
                                  "SUCCESS" if ok else "ERROR")
            self.logger.log_to_csv(action="Infra Deploy", resource_name=name,
                                   resource_type="Shortcut",
                                   status="created" if ok else "failed",
                                   success="successful" if ok else "failed")
            if ok:
                self.stats["shortcuts"]["created"] += 1
                ok_count += 1
            else:
                self.stats["shortcuts"]["failed"] += 1

        self.logger.write_log(f"Shortcuts: {ok_count}/{len(shortcuts)} succeeded.", "SUCCESS")
        return True

    # ------------------------------------------------------------------
    # 4. Spark Pool
    # ------------------------------------------------------------------
    def create_spark_pool(self) -> bool:
        pc = self._get_config_value("poolConfiguration", required=False)
        if not pc or not pc.get("name"):
            self.logger.write_log("No Spark pool config — skipping.", "WARNING")
            return True

        name = pc["name"]
        node_size = pc.get("nodeSize", "Medium")
        min_n = pc.get("autoScale.minNodeCount", 1)
        max_n = pc.get("autoScale.maxNodeCount", 10)

        pool_path = f"{self.target_workspace}.Workspace/.sparkpools/{name}.SparkPool"

        if self._exists(pool_path):
            self.logger.write_log(f"Spark pool '{name}' exists — updating properties.", "WARNING")
            self.stats["spark_pool"]["already_exists"] += 1
            for prop, val in [("nodeSize", node_size), ("autoScale.enabled", "True"),
                              ("autoScale.minNodeCount", str(min_n)),
                              ("autoScale.maxNodeCount", str(max_n))]:
                self._run(f'fab set "{pool_path}" -q {prop} -i {val} -f')
            self.logger.write_log(f"Spark pool '{name}' updated.", "SUCCESS")
        else:
            cmd = (f'fab create "{pool_path}" '
                   f'-P nodesize={node_size},autoScale.minnodecount={min_n},'
                   f'autoScale.maxnodecount={max_n}')
            ok, _, _ = self._run(cmd)
            self.logger.write_log(f"Spark pool '{name}' {'created' if ok else 'FAILED'}.",
                                  "SUCCESS" if ok else "ERROR")
            if ok:
                self.stats["spark_pool"]["created"] += 1
            else:
                self.stats["spark_pool"]["failed"] += 1
        return True

    # ------------------------------------------------------------------
    # 5. OneLake Folders
    # ------------------------------------------------------------------
    def create_onelake_folders(self) -> bool:
        fc = self._get_config_value("folderConfiguration", required=False)
        if not fc:
            self.logger.write_log("No folder config — skipping.", "WARNING")
            return True

        lh = self._get_config_value("fabricLakehouseName", required=False)
        if not lh:
            self.logger.write_log("Lakehouse name required for folder creation.", "ERROR")
            return False

        for key, folder in fc.items():
            if not folder:
                continue
            full = f"{self.target_workspace}.Workspace/{lh}.Lakehouse/Files/{folder}"
            if self._exists(full):
                self.logger.write_log(f"Folder '{folder}' already exists.", "WARNING")
                self.stats["folders"]["already_exists"] += 1
            else:
                ok, _, _ = self._run(f'fab mkdir "{full}"')
                self.logger.write_log(f"Folder '{folder}' {'created' if ok else 'FAILED'}.",
                                      "SUCCESS" if ok else "ERROR")
                if ok:
                    self.stats["folders"]["created"] += 1
                else:
                    self.stats["folders"]["failed"] += 1
        return True

    # ------------------------------------------------------------------
    # 6. Workspace Access (RBAC)
    # ------------------------------------------------------------------
    def configure_workspace_access(self) -> bool:
        ws_path = f"{self.target_workspace}.Workspace"
        identities = []

        spn = self._get_config_value("SPNObjectID", required=False)
        if spn and not self._is_placeholder(spn):
            identities.append(("SPN", spn, "admin"))

        ws_identity = self._get_config_value("fabricWorkspaceIdentity", required=False)
        if ws_identity and not self._is_placeholder(ws_identity):
            identities.append(("WorkspaceIdentity", ws_identity, "contributor"))

        if not identities:
            self.logger.write_log("No identities configured for access control.", "WARNING")
            return True

        for label, obj_id, role in identities:
            # Check existing access
            ok, acl_out, _ = self._run(f'fab acl list "{ws_path}"', capture=True)
            if ok and obj_id in acl_out:
                self.logger.write_log(f"{label} already has workspace access.", "WARNING")
                self.stats["workspace_access"]["already_exists"] += 1
                continue

            cmd = f'fab acl set "{ws_path}" -I {obj_id} -R {role} -f'
            ok, _, _ = self._run(cmd)
            self.logger.write_log(
                f"Granted {role} to {label} ({obj_id[:8]}...)." if ok
                else f"Failed to grant {role} to {label}.",
                "SUCCESS" if ok else "ERROR",
            )
            self.logger.log_to_csv(action="Infra Deploy",
                                   resource_name=f"Access-{label}",
                                   resource_type="WorkspaceAccess",
                                   status="created" if ok else "failed",
                                   success="successful" if ok else "failed")
            if ok:
                self.stats["workspace_access"]["created"] += 1
            else:
                self.stats["workspace_access"]["failed"] += 1
        return True

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------
    def deploy_all(self) -> bool:
        self.logger.write_log("=" * 60, "INFO")
        self.logger.write_log("FABRIC INFRASTRUCTURE DEPLOYMENT", "INFO")
        self.logger.write_log("=" * 60, "INFO")

        # Step 0 — Resolve workspace ID, identity, and lakehouse name
        if not self.resolve_config():
            self.logger.write_log("Config resolution failed — cannot continue.", "ERROR")
            return False

        steps = [
            ("LAKEHOUSE",        self.create_lakehouse),
            ("CONNECTION",       self.create_connection),
            ("SHORTCUTS",        self.create_shortcuts),
            ("SPARK POOL",       self.create_spark_pool),
            ("ONELAKE FOLDERS",  self.create_onelake_folders),
            ("WORKSPACE ACCESS", self.configure_workspace_access),
        ]

        all_ok = True
        for idx, (label, fn) in enumerate(steps, 1):
            self.logger.write_log(f"\n--- STEP {idx}: {label} ---", "INFO")
            if not fn():
                self.logger.write_log(f"{label} encountered issues — continuing.", "WARNING")
                all_ok = False

        # Deployment summary
        self.logger.write_log("\n" + "=" * 60, "INFO")
        self.logger.write_log("DEPLOYMENT STATISTICS", "INFO")
        self.logger.write_log("-" * 40, "INFO")
        
        for component, counts in self.stats.items():
            total = counts["created"] + counts["already_exists"]
            failed = counts["failed"]
            if total > 0 or failed > 0:
                label = component.replace("_", " ").title()
                status_parts = []
                if counts["created"] > 0:
                    status_parts.append(f"{counts['created']} created")
                if counts["already_exists"] > 0:
                    status_parts.append(f"{counts['already_exists']} existing")
                if failed > 0:
                    status_parts.append(f"{failed} failed")
                
                status_text = f"{label}: {', '.join(status_parts)}"
                log_level = "SUCCESS" if failed == 0 else "WARNING"
                self.logger.write_log(status_text, log_level)

        self.logger.write_log("\n" + "=" * 60, "INFO")
        self.logger.write_log(
            "Infrastructure deployment completed successfully!" if all_ok
            else "Infrastructure deployment completed with warnings — check logs.",
            "SUCCESS" if all_ok else "WARNING",
        )
        return all_ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fabric Infrastructure Deployment")
    parser.add_argument("--config", default=None, help="Path to fabric_config.json")
    parser.add_argument("--verbose_logging", "-v", action="store_true")
    parser.add_argument("--minimal_logging", action="store_true")
    args = parser.parse_args()

    deployer = FabricInfraDeployment(
        config_path=args.config,
        verbose_logging=args.verbose_logging,
        minimal_logging=args.minimal_logging,
    )
    ok = deployer.deploy_all()
    exit(0 if ok else 1)


if __name__ == "__main__":
    main()
