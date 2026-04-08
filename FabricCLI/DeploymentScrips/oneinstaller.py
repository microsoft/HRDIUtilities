#!/usr/bin/env python3
"""
One-Click Fabric Deployment Orchestrator
=========================================

Master script that chains deployment modules in the correct order:

    1. fabric_infra_deploy.py    →  Lakehouse, Connections, Shortcuts, Pools, ACL
    2. fabric_code_deploy.py     →  Notebooks, Pipelines, Semantic Models, Reports

Prerequisites:
    - Fill in Config/fabric_config.json with all environment values
    - Authenticate: fab auth login

Usage:
    python oneinstaller.py                       # Full deployment
    python oneinstaller.py --skip-infra          # Code artifacts only
    python oneinstaller.py --skip-code           # Infrastructure only
    python oneinstaller.py --verbose             # Detailed logging
    python oneinstaller.py --minimal             # SUCCESS/ERROR only
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


class FabricDeploymentOrchestrator:
    """Chains Fabric deployment scripts in dependency order."""

    def __init__(self, verbose: bool = False, minimal: bool = False,
                 skip_infra: bool = False, skip_code: bool = False):
        self.verbose = verbose
        self.minimal = minimal
        self.skip_infra = skip_infra
        self.skip_code = skip_code
        self.script_dir = Path(__file__).parent
        self.workspace_root = self.script_dir.parent
        self.config_path = self.workspace_root / "Config" / "fabric_config.json"

    def preflight_checks(self) -> bool:
        """Check Python version, Fabric CLI exists, and confirm workspace with user."""

        # 1. Check Python version >= 3.10
        major, minor = sys.version_info.major, sys.version_info.minor
        if major < 3 or (major == 3 and minor < 10):
            print(f"\n[ERROR] Python 3.10+ is required. Current version: {major}.{minor}")
            print("        Download from: https://www.python.org/downloads/\n")
            return False

        # 2. Check fab CLI is installed
        if not shutil.which("fab"):
            print("\n[ERROR] Fabric CLI ('fab') is not installed or not in PATH.")
            print("        Install it with:  pip install ms-fabric-cli")
            print("        Then authenticate: fab auth login")
            print("        See README.md for full setup instructions.\n")
            return False

        # 2. Load workspace name from config
        if not self.config_path.exists():
            print(f"\n[ERROR] Config file not found: {self.config_path}")
            return False

        with open(self.config_path, "r") as f:
            cfg = json.load(f)

        params = cfg.get("parameters", cfg)
        workspace = params.get("fabricWorkspaceName", {}).get("value", "").strip()
        if not workspace:
            print("\n[ERROR] 'fabricWorkspaceName' is not set in fabric_config.json.")
            return False

        # 3. Show confirmation and get user consent
        mode = "Full (Infrastructure + Code)"
        if self.skip_infra:
            mode = "Code Artifacts Only (--skip-infra)"
        elif self.skip_code:
            mode = "Infrastructure Only (--skip-code)"

        print(f"\n  Target Workspace : {workspace}")
        print(f"  Deployment Mode  : {mode}")
        print()
        answer = input("  Proceed with deployment? (Y/N): ").strip().upper()
        if answer != "Y":
            print("\n[INFO] Deployment cancelled by user.")
            return False

        return True

    def run_script(self, name: str) -> bool:
        path = self.script_dir / name
        if not path.exists():
            print(f"[ERROR] Script not found: {path}")
            return False

        cmd = [sys.executable, str(path)]
        if self.verbose:
            cmd.append("--verbose_logging")
        if self.minimal:
            cmd.append("--minimal_logging")

        print(f"\n{'='*60}")
        print(f"  Running: {name}")
        print(f"{'='*60}")
        try:
            result = subprocess.run(cmd, cwd=self.script_dir)
            return result.returncode == 0
        except Exception as exc:
            print(f"[ERROR] {name}: {exc}")
            return False

    def deploy(self) -> bool:
        print("=" * 60)
        print("  FABRIC ONE-CLICK DEPLOYMENT")
        print("=" * 60)

        # Pre-flight: check CLI + confirm workspace
        if not self.preflight_checks():
            return False

        # Step 1 — Infrastructure
        if not self.skip_infra:
            if not self.run_script("fabric_infra_deploy.py"):
                print("[WARNING] Infrastructure deployment had issues — continuing to code.")
        else:
            print("[INFO] Skipping infrastructure deployment.")

        # Step 2 — Code artifacts
        if not self.skip_code:
            if not self.run_script("fabric_code_deploy.py"):
                print("[WARNING] Code deployment had issues.")
        else:
            print("[INFO] Skipping code deployment.")

        print("\n" + "=" * 60)
        print("  DEPLOYMENT COMPLETE")
        print("=" * 60)
        return True


def main():
    parser = argparse.ArgumentParser(
        description="One-click Fabric deployment orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python oneinstaller.py                  # Full deployment
    python oneinstaller.py --skip-infra     # Code artifacts only
    python oneinstaller.py --skip-code      # Infrastructure only
    python oneinstaller.py --verbose        # Detailed logging
    python oneinstaller.py --minimal        # Minimal console output
        """,
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--minimal", action="store_true")
    parser.add_argument("--skip-infra", action="store_true", help="Skip infrastructure deployment")
    parser.add_argument("--skip-code", action="store_true", help="Skip code artifact deployment")
    args = parser.parse_args()

    if args.skip_infra and args.skip_code:
        print("[ERROR] Cannot skip both infrastructure and code.")
        sys.exit(1)

    orchestrator = FabricDeploymentOrchestrator(
        verbose=args.verbose,
        minimal=args.minimal,
        skip_infra=args.skip_infra,
        skip_code=args.skip_code,
    )
    ok = orchestrator.deploy()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
