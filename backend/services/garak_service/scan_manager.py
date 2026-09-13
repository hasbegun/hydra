"""
Scan manager for the garak service container.
Handles subprocess lifecycle: building commands, running garak CLI,
streaming progress, and cancellation.
"""
import asyncio
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Any

from progress_parser import ProgressParser

logger = logging.getLogger(__name__)

REPORTS_DIR = Path(os.environ.get("GARAK_REPORTS_DIR", "/data/garak_reports"))


class ScanState:
    """Tracks the state of a running scan."""

    MAX_OUTPUT_LINES = 200  # Keep last N lines for error diagnostics

    def __init__(self, scan_id: str, config: dict):
        self.scan_id = scan_id
        self.config = config
        self.status = "pending"
        self.progress = 0.0
        self.current_probe: Optional[str] = None
        self.completed_probes = 0
        self.total_probes = len(config.get("probes", []))
        self.current_iteration = 0
        self.total_iterations = 0
        self.passed = 0
        self.failed = 0
        self.elapsed_time: Optional[str] = None
        self.estimated_remaining: Optional[str] = None
        self.html_report_path: Optional[str] = None
        self.jsonl_report_path: Optional[str] = None
        self.error_message: Optional[str] = None
        self.created_at = datetime.now().isoformat()
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.process: Optional[asyncio.subprocess.Process] = None
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.output_lines: List[str] = []  # Recent output for diagnostics

    def to_dict(self) -> dict:
        return {
            "scan_id": self.scan_id,
            "status": self.status,
            "progress": self.progress,
            "current_probe": self.current_probe,
            "completed_probes": self.completed_probes,
            "total_probes": self.total_probes,
            "current_iteration": self.current_iteration,
            "total_iterations": self.total_iterations,
            "passed": self.passed,
            "failed": self.failed,
            "elapsed_time": self.elapsed_time,
            "estimated_remaining": self.estimated_remaining,
            "html_report_path": self.html_report_path,
            "jsonl_report_path": self.jsonl_report_path,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class ScanManager:
    """Manages garak scan subprocesses inside the garak container."""

    def __init__(self):
        self.active_scans: Dict[str, ScanState] = {}
        self.garak_path = self._find_garak()
        logger.info(f"Garak path: {self.garak_path}")
        logger.info(f"Reports directory: {REPORTS_DIR}")

    def _find_garak(self) -> Optional[str]:
        """Find garak executable in PATH or as module."""
        garak_path = shutil.which("garak")
        if garak_path:
            return garak_path

        common_paths = [
            "/usr/local/bin/garak",
            str(Path.home() / ".local" / "bin" / "garak"),
        ]
        for path in common_paths:
            if Path(path).exists():
                return path

        try:
            result = subprocess.run(
                ["python", "-m", "garak", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return "python -m garak"
        except Exception:
            pass

        logger.warning("garak not found")
        return None

    def check_garak_installed(self) -> bool:
        if not self.garak_path:
            return False
        try:
            cmd = (
                ["python", "-m", "garak", "--version"]
                if self.garak_path == "python -m garak"
                else [self.garak_path, "--version"]
            )
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False

    def get_garak_version(self) -> Optional[str]:
        if not self.garak_path:
            return None
        try:
            cmd = (
                ["python", "-m", "garak", "--version"]
                if self.garak_path == "python -m garak"
                else [self.garak_path, "--version"]
            )
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.error(f"Error getting garak version: {e}")
        return None

    def list_plugins(self, plugin_type: str) -> List[str]:
        """List available plugins of a specific type."""
        if not self.garak_path:
            return []

        command_map = {
            "probes": "--list_probes",
            "detectors": "--list_detectors",
            "generators": "--list_generators",
            "buffs": "--list_buffs",
        }
        cmd_arg = command_map.get(plugin_type)
        if not cmd_arg:
            return []

        try:
            cmd = (
                ["python", "-m", "garak", cmd_arg]
                if self.garak_path == "python -m garak"
                else [self.garak_path, cmd_arg]
            )
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                plugins = self._parse_plugin_list(result.stdout)
                logger.info(f"Found {len(plugins)} {plugin_type}")
                return plugins
            else:
                logger.error(f"Error listing {plugin_type}: {result.stderr}")
        except Exception as e:
            logger.error(f"Exception listing {plugin_type}: {e}")
        return []

    def _parse_plugin_list(self, output: str) -> List[str]:
        """Parse plugin list output from garak CLI."""
        plugins = []
        for line in output.split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("garak"):
                continue

            line_clean = re.sub(r'\x1b\[[0-9;]*m', '', line)
            line_clean = re.sub(r'\[[0-9;]*m', '', line_clean).strip()
            if not line_clean:
                continue

            parts = line_clean.split()
            if len(parts) >= 2 and parts[0].endswith(":"):
                plugin_name = re.sub(r'[^\w\.\-]', '', parts[1])
                if not plugin_name:
                    continue
                has_star = "\U0001f31f" in line
                has_dot = "." in plugin_name
                if has_dot or not has_star:
                    plugins.append(plugin_name)
            elif len(parts) >= 1:
                plugin_name = re.sub(r'[^\w\.\-]', '', parts[0])
                if plugin_name and "." in plugin_name:
                    plugins.append(plugin_name)
        return plugins

    def _build_command(self, config: dict) -> List[str]:
        """Build garak CLI command from scan configuration dict."""
        if not self.garak_path:
            raise RuntimeError("garak not found")

        cmd = (
            ["python", "-m", "garak"]
            if self.garak_path == "python -m garak"
            else [self.garak_path]
        )

        cmd.extend(["--target_type", config["target_type"]])
        cmd.extend(["--target_name", config["target_name"]])

        probes = config.get("probes", [])
        if probes:
            cleaned = [
                p.replace("probes.", "", 1) if p.startswith("probes.") else p
                for p in probes
            ]
            cmd.extend(["--probes", ",".join(cleaned)])

        if config.get("probe_tags"):
            cmd.extend(["--probe_tags", config["probe_tags"]])

        if config.get("system_prompt"):
            cmd.extend(["--system_prompt", config["system_prompt"]])

        if config.get("extended_detectors"):
            cmd.append("--extended_detectors")

        if config.get("deprefix"):
            cmd.append("--deprefix")

        verbose = config.get("verbose", 0)
        if verbose > 0:
            cmd.append("-" + "v" * verbose)

        if config.get("skip_unknown"):
            cmd.append("--skip_unknown")

        if config.get("buffs_include_original_prompt"):
            cmd.append("--buffs_include_original_prompt")

        if config.get("output_dir"):
            cmd.extend(["--output_dir", config["output_dir"]])

        if config.get("no_report"):
            cmd.append("--no_report")

        if config.get("continue_on_error"):
            cmd.append("--continue_on_error")

        if config.get("exclude_probes"):
            cmd.extend(["--exclude_probes", config["exclude_probes"]])

        if config.get("exclude_detectors"):
            cmd.extend(["--exclude_detectors", config["exclude_detectors"]])

        if config.get("timeout_per_probe") is not None:
            cmd.extend(["--timeout_per_probe", str(config["timeout_per_probe"])])

        if config.get("config_file"):
            cmd.extend(["--config", config["config_file"]])

        if config.get("hit_rate") is not None:
            cmd.extend(["--hit_rate", str(config["hit_rate"])])

        if config.get("report_threshold") is not None:
            cmd.extend(["--report_threshold", str(config["report_threshold"])])

        if config.get("collect_timing"):
            cmd.append("--collect_timing")

        detectors = config.get("detectors", [])
        if detectors:
            cleaned = [
                d.replace("detectors.", "", 1) if d.startswith("detectors.") else d
                for d in detectors
            ]
            cmd.extend(["--detectors", ",".join(cleaned)])

        buffs = config.get("buffs", [])
        if buffs:
            cleaned = [
                b.replace("buffs.", "", 1) if b.startswith("buffs.") else b
                for b in buffs
            ]
            cmd.extend(["--buffs", ",".join(cleaned)])

        cmd.extend(["--generations", str(config.get("generations", 5))])
        cmd.extend(["--eval_threshold", str(config.get("eval_threshold", 0.5))])

        if config.get("seed") is not None:
            cmd.extend(["--seed", str(config["seed"])])

        if config.get("parallel_requests"):
            cmd.extend(["--parallel_requests", str(config["parallel_requests"])])

        if config.get("parallel_attempts"):
            cmd.extend(["--parallel_attempts", str(config["parallel_attempts"])])

        # REST target flags
        if config.get("rest_endpoint"):
            cmd.extend(["--rest_endpoint", config["rest_endpoint"]])

        if config.get("rest_headers"):
            cmd.extend(["--rest_headers", json.dumps(config["rest_headers"])])

        if config.get("rest_body_template"):
            cmd.extend(["--rest_body_template", config["rest_body_template"]])

        if config.get("rest_response_json_field"):
            cmd.extend(["--rest_response_json_field", config["rest_response_json_field"]])

        # Generator options with Ollama host injection
        generator_type = config["target_type"].split(".")[0].lower()
        generator_options = {}
        if config.get("generator_options"):
            user_opts = dict(config["generator_options"])
            if generator_type in user_opts:
                generator_options = user_opts
            else:
                generator_options = {generator_type: user_opts}

        ollama_host = os.environ.get("OLLAMA_HOST")
        is_ollama = "ollama" in generator_type
        if ollama_host and is_ollama:
            if "ollama" not in generator_options:
                generator_options["ollama"] = {}
            if "host" not in generator_options["ollama"]:
                generator_options["ollama"]["host"] = ollama_host
                logger.info(f"Injecting Ollama host: {ollama_host}")

        if generator_options:
            cmd.extend(["--generator_options", json.dumps(generator_options)])

        if config.get("probe_options"):
            cmd.extend(["--probe_options", json.dumps(config["probe_options"])])

        if config.get("report_prefix"):
            cmd.extend(["--report_prefix", config["report_prefix"]])

        logger.info(f"Built command: {' '.join(cmd)}")
        return cmd

    async def start_scan(self, scan_id: str, config: dict) -> ScanState:
        """Start a new garak scan subprocess."""
        cmd = self._build_command(config)
        state = ScanState(scan_id, config)
        self.active_scans[scan_id] = state

        logger.info(f"[{scan_id}] Starting scan with command: {' '.join(cmd)}")
        logger.info(f"[{scan_id}] Config: {config}")
        asyncio.create_task(self._run_scan(state, cmd))
        return state

    async def _run_scan(self, state: ScanState, cmd: List[str]):
        """Execute garak scan as subprocess and feed events to the queue."""
        parser = ProgressParser(state.scan_id)

        try:
            state.status = "running"
            state.started_at = datetime.now().isoformat()
            await state.event_queue.put({
                "event_type": "status",
                "status": "running",
            })

            env = os.environ.copy()
            logger.info(
                f"[{state.scan_id}] Starting scan, "
                f"OLLAMA_HOST={env.get('OLLAMA_HOST', 'not set')}"
            )

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
                preexec_fn=os.setpgrp if hasattr(os, "setpgrp") else None,
            )
            state.process = process

            async def read_stream(stream):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="replace")

                    if "\r" in decoded:
                        parts = decoded.split("\r")
                        for part in parts:
                            part = part.strip()
                            if part:
                                await self._process_line(state, parser, part)
                    else:
                        decoded = decoded.strip()
                        if decoded:
                            await self._process_line(state, parser, decoded)

            await read_stream(process.stdout)
            returncode = await process.wait()

            state.completed_at = datetime.now().isoformat()

            if state.status == "failed":
                logger.error(
                    f"Scan {state.scan_id} failed: {state.error_message}"
                )
            elif returncode == 0:
                state.status = "completed"
                state.progress = 100.0

                # Upload report files to Minio (if configured)
                report_keys = {}
                try:
                    from report_uploader import upload_report_files
                    report_keys = upload_report_files(
                        state.scan_id,
                        REPORTS_DIR,
                        jsonl_path=state.jsonl_report_path,
                        html_path=state.html_report_path,
                    )
                except Exception as upload_err:
                    logger.warning(f"Report upload failed for {state.scan_id}: {upload_err}")

                await state.event_queue.put({
                    "event_type": "complete",
                    "status": "completed",
                    "passed": state.passed,
                    "failed": state.failed,
                    "report_keys": report_keys,
                })
                logger.info(f"Scan {state.scan_id} completed successfully")
            else:
                state.status = "failed"
                if not state.error_message:
                    # Include recent output for diagnostics
                    tail = state.output_lines[-20:] if state.output_lines else []
                    tail_str = "\n".join(tail)
                    state.error_message = (
                        f"Process exited with code {returncode}. "
                        f"Last output:\n{tail_str}"
                    )
                await state.event_queue.put({
                    "event_type": "error",
                    "message": state.error_message,
                })
                logger.error(
                    f"Scan {state.scan_id} failed with code {returncode}. "
                    f"Output tail: {state.output_lines[-10:]}"
                )

        except Exception as e:
            logger.error(f"Error running scan {state.scan_id}: {e}")
            state.status = "failed"
            state.error_message = str(e)
            state.completed_at = datetime.now().isoformat()
            await state.event_queue.put({
                "event_type": "error",
                "message": str(e),
            })

        # Signal end of stream
        await state.event_queue.put(None)

    async def _process_line(
        self, state: ScanState, parser: ProgressParser, line: str
    ):
        """Parse a line and update state + event queue."""
        # Keep recent output for error diagnostics
        state.output_lines.append(line)
        if len(state.output_lines) > ScanState.MAX_OUTPUT_LINES:
            state.output_lines = state.output_lines[-ScanState.MAX_OUTPUT_LINES:]

        event = parser.parse_line(line)
        if event:
            # Update local state from event
            etype = event["event_type"]
            if etype == "progress":
                state.current_probe = event.get("probe")
                state.progress = float(event.get("percent", state.progress))
                state.current_iteration = event.get("current", 0)
                state.total_iterations = event.get("total", 0)
                state.elapsed_time = event.get("elapsed")
                state.estimated_remaining = event.get("remaining")
            elif etype == "probe_count":
                state.completed_probes = event.get("completed", 0)
                state.total_probes = event.get("total", 0)
            elif etype == "current_probe":
                state.current_probe = event.get("probe")
            elif etype == "result":
                state.passed = event.get("total_passed", state.passed)
                state.failed = event.get("total_failed", state.failed)
            elif etype == "report":
                if event.get("report_type") == "html":
                    state.html_report_path = event.get("path")
                elif event.get("report_type") == "jsonl":
                    state.jsonl_report_path = event.get("path")
            elif etype == "error":
                state.status = "failed"
                state.error_message = event.get("message")

            # Add raw line for the backend's workflow analyzer
            event["raw_line"] = line
            await state.event_queue.put(event)
        else:
            # Send raw output lines too
            await state.event_queue.put({
                "event_type": "output",
                "line": line,
                "raw_line": line,
            })

    async def stream_progress(self, scan_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield progress events for a scan. Blocks until events are available."""
        state = self.active_scans.get(scan_id)
        if not state:
            return

        while True:
            event = await state.event_queue.get()
            if event is None:
                # End of stream
                break
            yield event

    async def cancel_scan(self, scan_id: str) -> bool:
        """Cancel a running scan by killing its process group."""
        state = self.active_scans.get(scan_id)
        if not state:
            return False
        if state.status not in ("running", "pending"):
            return False

        process = state.process
        if not process:
            return False

        try:
            pid = process.pid
            logger.info(f"[{scan_id}] Canceling scan (PID: {pid})")

            if process.returncode is not None:
                state.status = "cancelled"
                state.completed_at = datetime.now().isoformat()
                await state.event_queue.put(None)
                return True

            # Kill process group
            if hasattr(os, "killpg"):
                try:
                    pgid = os.getpgid(pid)
                    os.killpg(pgid, signal.SIGTERM)
                    logger.info(f"[{scan_id}] Sent SIGTERM to process group {pgid}")
                except (ProcessLookupError, OSError) as e:
                    logger.warning(f"[{scan_id}] killpg failed: {e}")

            try:
                process.terminate()
            except ProcessLookupError:
                pass

            await asyncio.sleep(1)

            if process.returncode is None:
                logger.info(f"[{scan_id}] Force killing")
                if hasattr(os, "killpg"):
                    try:
                        pgid = os.getpgid(pid)
                        os.killpg(pgid, signal.SIGKILL)
                    except (ProcessLookupError, OSError):
                        pass
                try:
                    process.kill()
                except ProcessLookupError:
                    pass

            await asyncio.sleep(0.5)

            state.status = "cancelled"
            state.completed_at = datetime.now().isoformat()
            await state.event_queue.put(None)
            logger.info(f"[{scan_id}] Scan cancelled")
            return True

        except Exception as e:
            logger.error(f"[{scan_id}] Error cancelling scan: {e}")
            state.status = "cancelled"
            state.completed_at = datetime.now().isoformat()
            await state.event_queue.put(None)
            return False

    def get_status(self, scan_id: str) -> Optional[dict]:
        state = self.active_scans.get(scan_id)
        if state:
            return state.to_dict()
        return None

    def list_active_scans(self) -> List[dict]:
        return [s.to_dict() for s in self.active_scans.values()]

    def list_report_files(self) -> List[str]:
        """List all report files in the reports directory."""
        if not REPORTS_DIR.exists():
            return []
        return [
            f.name for f in REPORTS_DIR.iterdir()
            if f.is_file() and (f.suffix in (".html", ".jsonl"))
        ]


# Global instance
scan_manager = ScanManager()
