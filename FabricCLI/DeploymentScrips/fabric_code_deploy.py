#!/usr/bin/env python3
"""
Fabric Code Deployment
=======================

Deploys Fabric code artifacts from a local source directory into a target
workspace. Handles the complete pipeline for each artifact type:

    1. Copy source files to a temp staging directory
    2. Replace ##placeholder## tokens with values from fabric_config.json
    3. Deploy to the Fabric workspace using ``fab import``

Supported artifacts (deployed in dependency order):
    - Semantic Models  (.SemanticModel / .tmdl)
    - Reports          (.Report / .pbir / .json)
    - Notebooks        (.Notebook / .ipynb / .py)
    - Pipelines        (.DataPipeline / pipeline-content.json)

Usage:
    python fabric_code_deploy.py
    python fabric_code_deploy.py --verbose_logging
    python fabric_code_deploy.py --minimal_logging
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
from shared_logger import SharedLogger


class FabricCodeDeployment:
    """Config-driven deployment of Fabric code artifacts."""

    def __init__(self, workspace_root: str, config_path: str = None,
                 minimal_logging: bool = False, verbose_logging: bool = False):
        self.workspace_root = Path(workspace_root)
        self.config_path = (
            Path(config_path) if config_path
            else self.workspace_root / "Config" / "fabric_config.json"
        )
        self.source_path = self.workspace_root / "Code" / "Fabric"
        self.temp_path = self.workspace_root / "temp"

        self.minimal_logging = minimal_logging
        self.verbose_logging = verbose_logging

        self.logger = SharedLogger("fabric_code_deploy.py", str(self.workspace_root), minimal_logging)

        self.deployment_paths: Dict[str, Path] = {
            "notebooks": self.temp_path / "notebooks",
            "pipelines": self.temp_path / "pipelines",
            "models":    self.temp_path / "models",
            "reports":   self.temp_path / "reports",
        }
        self.config_data: dict = {}
        self.replacement_map: Dict[str, str] = {}
        self.target_workspace: str = ""

        self.stats = {
            "notebooks":       {"planned": 0, "created": 0, "failed": 0},
            "pipelines":       {"planned": 0, "created": 0, "failed": 0},
            "semantic_models": {"planned": 0, "created": 0, "failed": 0},
            "reports":         {"planned": 0, "created": 0, "failed": 0},
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _clean_ws(name: str) -> str:
        for p in ("/workspaces/",):
            if name.startswith(p):
                name = name[len(p):]
        return name.rstrip("/").replace(".Workspace", "")

    def _run(self, cmd: str, capture: bool = False) -> Union[bool, Tuple[bool, str]]:
        """Run a shell command. Returns bool or (bool, stdout) when capture=True."""
        if self.verbose_logging:
            self.logger.write_log(f"[DEBUG] {cmd}", "DEBUG")
        timeout = 60 if capture else 300
        try:
            r = subprocess.run(cmd, shell=True, capture_output=capture,
                               text=True if capture else False,
                               timeout=timeout, cwd=None)
            if capture:
                return r.returncode == 0, (r.stdout.strip() if r.stdout else "")
            return r.returncode == 0
        except subprocess.TimeoutExpired:
            return (False, "") if capture else False
        except Exception:
            return (False, "") if capture else False

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------
    def load_config(self) -> bool:
        try:
            if not self.config_path.exists():
                self.logger.write_log(f"Config not found: {self.config_path}", "ERROR")
                return False

            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config_data = json.load(f)

            ws = self.config_data.get("parameters", {}).get("fabricWorkspaceName", {}).get("value", "")
            if not ws:
                self.logger.write_log("fabricWorkspaceName missing in config.", "ERROR")
                return False
            self.target_workspace = self._clean_ws(ws)

            # Build replacement map from all simple parameters
            for key, param in self.config_data.get("parameters", {}).items():
                if key == "modelConfiguration":
                    continue
                if isinstance(param, dict) and "value" in param:
                    v = param["value"]
                    self.replacement_map[f"##{key}##"] = (
                        json.dumps(v, indent=2) if isinstance(v, (dict, list)) else str(v)
                    )

            self.logger.write_log(f"Config loaded — workspace: {self.target_workspace}", "SUCCESS")
            return True
        except Exception as exc:
            self.logger.write_log(f"Error loading config: {exc}", "ERROR")
            return False

    def create_temp_dirs(self) -> bool:
        for p in self.deployment_paths.values():
            if p.exists():
                shutil.rmtree(p)
            p.mkdir(parents=True, exist_ok=True)
        self.logger.write_log("Temp directories created.", "SUCCESS")
        return True

    # ------------------------------------------------------------------
    # Placeholder replacement
    # ------------------------------------------------------------------
    def replace_placeholders(self, content: str) -> Tuple[str, int]:
        """Replace ##param## tokens with config values."""
        count = 0
        for token, value in self.replacement_map.items():
            if token in content:
                content = content.replace(token, value)
                count += 1
        return content, count

    def replace_notebook_ids_in_pipeline(self, content: str) -> Tuple[str, int]:
        """Replace ##NotebookName## with real notebook IDs from config."""
        count = 0
        nb_cfg = self.config_data.get("parameters", {}).get("notebookConfiguration", {}).get("value", {})
        for nb in nb_cfg.get("notebooks", []):
            token = f"##{nb.get('name', '')}##"
            nb_id = nb.get("id", "")
            if token and nb_id and token in content:
                content = content.replace(token, nb_id)
                count += 1
        return content, count

    def replace_model_id_in_pbir(self, content: str, report_name: str) -> Tuple[str, int]:
        """Replace ##semanticModelId## with the matching model ID."""
        if "##semanticModelId##" not in content:
            return content, 0
        models = (self.config_data.get("parameters", {})
                  .get("modelConfiguration", {}).get("value", {}).get("models", []))
        base = report_name.replace(".Report", "")
        for m in models:
            if m.get("name") == base:
                content = content.replace("##semanticModelId##", m["id"])
                return content, 1
        return content, 0

    # ------------------------------------------------------------------
    # Deploy a single item
    # ------------------------------------------------------------------
    def deploy_item(self, local_path: str, target_path: str, is_notebook: bool = False) -> bool:
        if not os.path.exists(local_path):
            self.logger.write_log(f"  [SKIP] Not found: {local_path}", "WARNING")
            return False

        parts = target_path.split("/")
        if parts and not parts[0].endswith(".Workspace"):
            parts[0] += ".Workspace"
        target_path = "/".join(parts)

        cmd = f'fab import "{target_path}" -f -i "{local_path}"'
        self.logger.write_log(f"  [ACTION] {cmd}", "INFO")

        ok = self._run(cmd)

        artifact = os.path.basename(local_path)
        if ok:
            self.logger.write_log(f"  [SUCCESS] {artifact}", "SUCCESS")
        else:
            self.logger.write_log(f"  [ERROR] {artifact}", "ERROR")
        return ok

    # ------------------------------------------------------------------
    # Per-artifact pipelines
    # ------------------------------------------------------------------
    def process_and_deploy_semantic_models(self) -> bool:
        self.logger.write_log("\n" + "=" * 60, "INFO")
        self.logger.write_log("SEMANTIC MODELS", "INFO")

        src = self.source_path / "Models"
        if not src.exists():
            self.logger.write_log("No Models directory — skipping.", "WARNING")
            return True

        folders = [f for f in src.iterdir() if f.is_dir() and f.name.endswith(".SemanticModel")]
        if not folders:
            return True

        self.stats["semantic_models"]["planned"] = len(folders)
        ok_count = 0

        for folder in folders:
            dest = self.deployment_paths["models"] / folder.name
            shutil.copytree(folder, dest, dirs_exist_ok=True)

            # Replace placeholders in .tmdl files
            for tmdl in dest.rglob("*.tmdl"):
                text = tmdl.read_text(encoding="utf-8")
                text, _ = self.replace_placeholders(text)
                tmdl.write_text(text, encoding="utf-8")

            target = f"{self.target_workspace}/{folder.name}"
            if self.deploy_item(str(dest), re.sub(r"/+", "/", target)):
                ok_count += 1
                # Capture deployed model ID for report binding
                clean = folder.name.replace(".SemanticModel", "")
                ok_id, mid = self._run(
                    f'fab get "{self.target_workspace}.Workspace/{clean}.SemanticModel" -q id',
                    capture=True,
                )
                if ok_id and mid:
                    self._save_model_id(folder.name, mid)

        self.stats["semantic_models"]["created"] = ok_count
        self.logger.write_log(f"Models: {ok_count}/{len(folders)} deployed.", "SUCCESS")
        return True

    def process_and_deploy_reports(self) -> bool:
        self.logger.write_log("\n" + "=" * 60, "INFO")
        self.logger.write_log("REPORTS", "INFO")

        src = self.source_path / "Reports"
        if not src.exists():
            self.logger.write_log("No Reports directory — skipping.", "WARNING")
            return True

        folders = [f for f in src.iterdir() if f.is_dir() and f.name.endswith(".Report")]
        if not folders:
            return True

        self.stats["reports"]["planned"] = len(folders)
        ok_count = 0

        for folder in folders:
            dest = self.deployment_paths["reports"] / folder.name
            shutil.copytree(folder, dest, dirs_exist_ok=True)

            # .pbir — semantic model ID replacement + general placeholders
            for pbir in dest.rglob("*.pbir"):
                text = pbir.read_text(encoding="utf-8")
                text, _ = self.replace_model_id_in_pbir(text, folder.name)
                text, _ = self.replace_placeholders(text)
                pbir.write_text(text, encoding="utf-8")

            # .json — general placeholders
            for jf in dest.rglob("*.json"):
                text = jf.read_text(encoding="utf-8")
                text, _ = self.replace_placeholders(text)
                jf.write_text(text, encoding="utf-8")

            target = f"{self.target_workspace}/{folder.name}"
            if self.deploy_item(str(dest), re.sub(r"/+", "/", target)):
                ok_count += 1

        self.stats["reports"]["created"] = ok_count
        self.logger.write_log(f"Reports: {ok_count}/{len(folders)} deployed.", "SUCCESS")
        return True

    def process_and_deploy_notebooks(self) -> bool:
        self.logger.write_log("\n" + "=" * 60, "INFO")
        self.logger.write_log("NOTEBOOKS", "INFO")

        src = self.source_path / "Notebooks"
        if not src.exists():
            self.logger.write_log("No Notebooks directory — skipping.", "WARNING")
            return True

        folders = [f for f in src.iterdir() if f.is_dir() and f.name.endswith(".Notebook")]
        if not folders:
            return True

        self.stats["notebooks"]["planned"] = len(folders)
        ok_count = 0

        for folder in folders:
            dest = self.deployment_paths["notebooks"] / folder.name
            shutil.copytree(folder, dest, dirs_exist_ok=True)

            # Replace placeholders in .ipynb and .py files
            for ext in ("*.ipynb", "*.py"):
                for f in dest.rglob(ext):
                    text = f.read_text(encoding="utf-8")
                    text, _ = self.replace_placeholders(text)
                    f.write_text(text, encoding="utf-8")

            target = f"{self.target_workspace}/{folder.name}"
            if self.deploy_item(str(dest), re.sub(r"/+", "/", target), is_notebook=True):
                ok_count += 1
                # Capture notebook ID for pipeline binding
                clean = folder.name.replace(".Notebook", "")
                ok_id, nid = self._run(
                    f'fab get "{self.target_workspace}.Workspace/{clean}.Notebook" -q id',
                    capture=True,
                )
                if ok_id and nid:
                    self._save_notebook_id(folder.name, nid)

        self.stats["notebooks"]["created"] = ok_count
        self.logger.write_log(f"Notebooks: {ok_count}/{len(folders)} deployed.", "SUCCESS")
        return True

    def process_and_deploy_pipelines(self) -> bool:
        self.logger.write_log("\n" + "=" * 60, "INFO")
        self.logger.write_log("PIPELINES", "INFO")

        src = self.source_path / "Pipelines"
        if not src.exists():
            self.logger.write_log("No Pipelines directory — skipping.", "WARNING")
            return True

        folders = [f for f in src.iterdir() if f.is_dir() and f.name.endswith(".DataPipeline")]
        if not folders:
            return True

        self.stats["pipelines"]["planned"] = len(folders)
        ok_count = 0

        for folder in folders:
            dest = self.deployment_paths["pipelines"] / folder.name
            shutil.copytree(folder, dest, dirs_exist_ok=True)

            pjson = dest / "pipeline-content.json"
            if pjson.exists():
                text = pjson.read_text(encoding="utf-8")
                text, _ = self.replace_notebook_ids_in_pipeline(text)
                text, _ = self.replace_placeholders(text)
                pjson.write_text(text, encoding="utf-8")

            target = f"{self.target_workspace}/{folder.name}"
            if self.deploy_item(str(dest), re.sub(r"/+", "/", target)):
                ok_count += 1

        self.stats["pipelines"]["created"] = ok_count
        self.logger.write_log(f"Pipelines: {ok_count}/{len(folders)} deployed.", "SUCCESS")
        return True

    # ------------------------------------------------------------------
    # Config updaters (save IDs for cross-artifact references)
    # ------------------------------------------------------------------
    def _save_model_id(self, model_name: str, model_id: str):
        with open(self.config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        p = cfg.setdefault("parameters", {})
        mc = p.setdefault("modelConfiguration", {"value": {"models": []}})
        models = mc["value"].setdefault("models", [])

        clean = model_name.replace(".SemanticModel", "")
        for m in models:
            if m.get("name") == clean:
                m["id"] = model_id
                break
        else:
            models.append({"name": clean, "id": model_id})

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        self.config_data = cfg  # reload in memory
        self.logger.write_log(f"  Config updated: model '{clean}' → {model_id}", "SUCCESS")

    def _save_notebook_id(self, nb_name: str, nb_id: str):
        with open(self.config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        p = cfg.setdefault("parameters", {})
        nc = p.setdefault("notebookConfiguration", {"value": {"notebooks": []}})
        notebooks = nc["value"].setdefault("notebooks", [])

        clean = nb_name.replace(".Notebook", "")
        for n in notebooks:
            if n.get("name") == clean:
                n["id"] = nb_id
                break
        else:
            notebooks.append({"name": clean, "id": nb_id})

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        self.config_data = cfg
        self.logger.write_log(f"  Config updated: notebook '{clean}' → {nb_id}", "SUCCESS")

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------
    def deploy_all(self) -> bool:
        self.logger.write_log("Fabric Code Deployment Starting", "INFO")

        if not self.load_config():
            return False
        if not self.create_temp_dirs():
            return False

        # Deploy in dependency order:
        #   semantic models → reports → notebooks → pipelines
        ok = True
        ok &= self.process_and_deploy_semantic_models()
        ok &= self.process_and_deploy_reports()
        ok &= self.process_and_deploy_notebooks()
        ok &= self.process_and_deploy_pipelines()

        # Summary
        self.logger.write_log("\nDEPLOYMENT STATISTICS", "INFO")
        self.logger.write_log("-" * 40, "INFO")
        for kind, s in self.stats.items():
            if s["planned"] > 0:
                label = kind.replace("_", " ").title()
                self.logger.write_log(
                    f"{label}: {s['created']}/{s['planned']} deployed",
                    "SUCCESS" if s["created"] == s["planned"] else "WARNING",
                )

        self.logger.write_log(
            "\nCode deployment completed successfully!" if ok
            else "\nCode deployment completed with errors — check logs.",
            "SUCCESS" if ok else "ERROR",
        )
        return ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fabric Code Deployment")
    parser.add_argument("--config", default=None, help="Path to fabric_config.json")
    parser.add_argument("--source", default=None, help="Path to source Fabric artifact directory")
    parser.add_argument("--verbose_logging", "-v", action="store_true")
    parser.add_argument("--minimal_logging", action="store_true")
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    workspace_root = script_dir.parent

    deployer = FabricCodeDeployment(
        str(workspace_root),
        config_path=args.config,
        minimal_logging=args.minimal_logging,
        verbose_logging=args.verbose_logging,
    )

    if args.source:
        deployer.source_path = Path(args.source)

    ok = deployer.deploy_all()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
