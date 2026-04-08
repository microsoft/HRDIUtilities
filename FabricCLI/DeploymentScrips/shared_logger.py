#!/usr/bin/env python3
"""
Shared Logger Module for Fabric Deployment
==========================================

Provides consistent logging across all deployment scripts:
- Console output with color-coded severity levels
- Daily running log files (ddmmyyyy format)
- CSV audit trail for all deployment actions

Usage:
    from shared_logger import SharedLogger
    logger = SharedLogger("my_script.py", "/path/to/workspace")
    logger.write_log("Deployment started", "INFO")
    logger.log_to_csv(action="Deploy", resource_name="lakehouse", ...)
"""

import csv
from pathlib import Path
from datetime import datetime


class SharedLogger:
    """Shared logging with console output, running log, and CSV audit trail."""

    def __init__(self, script_name: str, workspace_root: str, minimal_logging: bool = False):
        """
        Args:
            script_name:     Name of the calling script (used in CSV logs).
            workspace_root:  Root directory of the workspace.
            minimal_logging: When True, console shows only SUCCESS/ERROR/WARNING.
        """
        self.script_name = script_name
        self.workspace_root = Path(workspace_root)
        self.minimal_logging = minimal_logging

        self.warning_count = 0
        self.error_count = 0

        # Log directory
        self.log_dir = self.workspace_root / "Logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Daily file names
        date_str = datetime.now().strftime("%d%m%Y")
        self.running_log_file = self.log_dir / f"runninglog_{date_str}.txt"
        self.csv_log_path = self.log_dir / f"deployment_log_{date_str}.csv"

        self._init_running_log()
        self._init_csv_log()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------
    def _init_running_log(self):
        try:
            mode = "a" if self.running_log_file.exists() else "w"
            with open(self.running_log_file, mode, encoding="utf-8") as f:
                if mode == "w":
                    f.write("Fabric Deployment Suite — Daily Log\n")
                    f.write("=" * 60 + "\n")
                    f.write(f"Date: {datetime.now().strftime('%Y-%m-%d')}\n")
                    f.write("=" * 60 + "\n")
                f.write(f"\n{'='*60}\n")
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] Starting {self.script_name}\n")
                f.write(f"{'='*60}\n")
        except Exception as exc:
            print(f"Warning: could not initialise running log: {exc}")

    def _init_csv_log(self):
        headers = [
            "Timestamp", "Platform", "ScriptName", "ResourceName",
            "ResourceType", "Status", "Success", "ErrorReason",
            "ExecutionCommand", "Action", "RemediationSteps",
        ]
        try:
            needs_create = not self.csv_log_path.exists()
            if not needs_create:
                with open(self.csv_log_path, "r", newline="", encoding="utf-8") as f:
                    first_row = next(csv.reader(f), None)
                    if first_row is None or len(first_row) != len(headers):
                        needs_create = True
            if needs_create:
                with open(self.csv_log_path, "w", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow(headers)
        except Exception as exc:
            print(f"Warning: could not initialise CSV log: {exc}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def write_log(self, message: str, level: str = "INFO"):
        """Write a message to the console and running log file."""
        if level == "WARNING":
            self.warning_count += 1
        elif level == "ERROR":
            self.error_count += 1

        colors = {
            "INFO": "\033[37m",
            "SUCCESS": "\033[32m",
            "ERROR": "\033[31m",
            "WARNING": "\033[33m",
            "DEBUG": "\033[90m",
        }
        reset = "\033[0m"
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Always write to file
        try:
            with open(self.running_log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception:
            pass

        # Console output respects minimal_logging
        if self.minimal_logging and level not in ("SUCCESS", "ERROR", "WARNING"):
            return
        color = colors.get(level, colors["INFO"])
        print(f"{color}{message}{reset}")

    def log_to_csv(
        self,
        action: str,
        resource_name: str = "",
        resource_type: str = "",
        status: str = "",
        success: str = "successful",
        error_reason: str = "",
        execution_command: str = "",
        remediation_steps: str = "",
    ):
        """Append one row to the CSV audit log."""
        try:
            with open(self.csv_log_path, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Fabric",
                    self.script_name,
                    resource_name,
                    resource_type,
                    status,
                    success,
                    error_reason,
                    execution_command,
                    action,
                    remediation_steps,
                ])
        except Exception:
            pass

    def has_warnings(self) -> bool:
        return self.warning_count > 0

    def has_errors(self) -> bool:
        return self.error_count > 0

    def get_issue_counts(self) -> tuple:
        return self.warning_count, self.error_count
