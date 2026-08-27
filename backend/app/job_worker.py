from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import Event, RLock
from typing import Any, Mapping, Sequence


class JobState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"


@dataclass
class _Job:
    job_id: str
    kind: str
    command: tuple[str, ...]
    files: dict[str, str]
    timeout_seconds: float
    state: JobState = JobState.QUEUED
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    created_monotonic: float = field(default_factory=time.monotonic)
    started_monotonic: float | None = None
    finished_monotonic: float | None = None
    workspace_deleted: bool = False
    cancel_event: Event = field(default_factory=Event)
    process: subprocess.Popen[str] | None = None


class LocalBoundedJobWorker:
    """Bounded no-shell local worker with cancellation, timeout and temp workspaces.

    Jobs have a lifecycle, concurrency bound, executable allowlist, isolated
    temporary cwd, bounded returned output, path-safe input materialization and
    active cancellation. ``communicate()`` drains child pipes while the process
    runs so verbose children cannot deadlock on small platform pipe buffers.
    Cancellation is re-checked immediately after spawn to close the race where
    an operator cancels after RUNNING is published but before ``job.process`` is
    visible. This remains a host OS process, not a container/VM/seccomp sandbox.
    """

    def __init__(
        self,
        *,
        allowed_executables: Sequence[str],
        max_workers: int = 2,
        default_timeout_seconds: float = 30.0,
        max_output_bytes: int = 256_000,
    ) -> None:
        if max_workers < 1 or max_workers > 32:
            raise ValueError("max_workers must be in [1, 32]")
        if default_timeout_seconds <= 0 or default_timeout_seconds > 3600:
            raise ValueError("default_timeout_seconds must be in (0, 3600]")
        if max_output_bytes < 1024 or max_output_bytes > 16_000_000:
            raise ValueError("max_output_bytes must be in [1024, 16000000]")
        resolved: set[str] = set()
        for executable in allowed_executables:
            path = shutil.which(executable) if not Path(executable).is_absolute() else executable
            if path:
                resolved.add(str(Path(path).resolve()))
        if not resolved:
            raise ValueError("at least one allowed executable must resolve")
        self.allowed_executables = frozenset(resolved)
        self.default_timeout_seconds = float(default_timeout_seconds)
        self.max_output_bytes = int(max_output_bytes)
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="morpheus-worker")
        self._jobs: dict[str, _Job] = {}
        self._lock = RLock()

    def submit(
        self,
        *,
        kind: str,
        command: Sequence[str],
        files: Mapping[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        if not kind or len(kind) > 128:
            raise ValueError("kind must contain 1-128 characters")
        normalized_command = self._validate_command(command)
        materialized_files = self._validate_files(files or {})
        timeout = self.default_timeout_seconds if timeout_seconds is None else float(timeout_seconds)
        if timeout <= 0 or timeout > 3600:
            raise ValueError("timeout_seconds must be in (0, 3600]")
        job_id = f"job-{secrets.token_hex(12)}"
        job = _Job(
            job_id=job_id,
            kind=kind,
            command=normalized_command,
            files=materialized_files,
            timeout_seconds=timeout,
        )
        with self._lock:
            self._jobs[job_id] = job
        self._executor.submit(self._run, job_id)
        return self.get(job_id)

    def get(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            try:
                job = self._jobs[job_id]
            except KeyError as exc:
                raise KeyError(f"unknown job: {job_id}") from exc
            return self._view(job)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._view(self._jobs[key]) for key in sorted(self._jobs)]

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            try:
                job = self._jobs[job_id]
            except KeyError as exc:
                raise KeyError(f"unknown job: {job_id}") from exc
            if job.state in {JobState.SUCCEEDED, JobState.FAILED, JobState.TIMED_OUT, JobState.CANCELLED}:
                return self._view(job)
            job.cancel_event.set()
            process = job.process
        if process is not None and process.poll() is None:
            self._terminate(process)
        return self.get(job_id)

    def wait(self, job_id: str, *, timeout_seconds: float = 10.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        terminal = {JobState.SUCCEEDED.value, JobState.FAILED.value, JobState.TIMED_OUT.value, JobState.CANCELLED.value}
        while time.monotonic() < deadline:
            current = self.get(job_id)
            if current["state"] in terminal:
                return current
            time.sleep(0.01)
        raise TimeoutError(f"job did not finish within wait timeout: {job_id}")

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=True)

    def _run(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if job.cancel_event.is_set():
                job.state = JobState.CANCELLED
                job.finished_monotonic = time.monotonic()
                return
            job.state = JobState.RUNNING
            job.started_monotonic = time.monotonic()

        with tempfile.TemporaryDirectory(prefix="morpheus-job-") as raw_workspace:
            workspace = Path(raw_workspace).resolve()
            try:
                for relative, content in job.files.items():
                    destination = (workspace / relative).resolve()
                    if workspace not in destination.parents:
                        raise ValueError("job input path escaped workspace")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text(content, encoding="utf-8")

                environment = self._safe_environment(raw_workspace)
                process = subprocess.Popen(
                    list(job.command),
                    cwd=workspace,
                    env=environment,
                    shell=False,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    start_new_session=(os.name != "nt"),
                )
                with self._lock:
                    job.process = process
                    cancelled_after_spawn = job.cancel_event.is_set()

                if cancelled_after_spawn:
                    self._terminate(process)
                    stdout, stderr = process.communicate(timeout=2)
                    terminal_state = JobState.CANCELLED
                else:
                    try:
                        stdout, stderr = process.communicate(timeout=job.timeout_seconds)
                        terminal_state = (
                            JobState.CANCELLED
                            if job.cancel_event.is_set()
                            else (JobState.SUCCEEDED if process.returncode == 0 else JobState.FAILED)
                        )
                    except subprocess.TimeoutExpired:
                        self._terminate(process)
                        stdout, stderr = process.communicate(timeout=2)
                        terminal_state = JobState.CANCELLED if job.cancel_event.is_set() else JobState.TIMED_OUT

                with self._lock:
                    job.state = terminal_state
                    job.returncode = process.returncode
                    job.stdout = self._truncate(stdout)
                    job.stderr = self._truncate(stderr)
                    job.process = None
                    job.finished_monotonic = time.monotonic()
            except Exception as exc:
                with self._lock:
                    job.state = JobState.CANCELLED if job.cancel_event.is_set() else JobState.FAILED
                    job.returncode = None
                    job.stderr = self._truncate(str(exc))
                    job.process = None
                    job.finished_monotonic = time.monotonic()
            finally:
                with self._lock:
                    job.workspace_deleted = True

    def _validate_command(self, command: Sequence[str]) -> tuple[str, ...]:
        if not command or len(command) > 256:
            raise ValueError("command must contain 1-256 arguments")
        executable_raw = str(command[0])
        executable = shutil.which(executable_raw) if not Path(executable_raw).is_absolute() else executable_raw
        if not executable:
            raise ValueError(f"executable does not resolve: {executable_raw}")
        resolved = str(Path(executable).resolve())
        if resolved not in self.allowed_executables:
            raise ValueError("executable is not permitted by worker policy")
        normalized = [resolved]
        for raw in command[1:]:
            value = str(raw)
            if "\x00" in value or len(value) > 16_384:
                raise ValueError("invalid command argument")
            normalized.append(value)
        return tuple(normalized)

    @staticmethod
    def _validate_files(files: Mapping[str, str]) -> dict[str, str]:
        if len(files) > 128:
            raise ValueError("too many input files")
        normalized: dict[str, str] = {}
        total = 0
        for raw_path, raw_content in files.items():
            path = Path(str(raw_path))
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise ValueError("job input paths must be relative and may not contain '..'")
            content = str(raw_content)
            total += len(content.encode("utf-8"))
            if total > 8_000_000:
                raise ValueError("job input files exceed 8 MB policy")
            normalized[path.as_posix()] = content
        return normalized

    @staticmethod
    def _safe_environment(workspace: str) -> dict[str, str]:
        keep = ("PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "HOME", "USERPROFILE")
        environment = {key: os.environ[key] for key in keep if key in os.environ}
        environment.update({"LANG": "C", "LC_ALL": "C", "TMPDIR": workspace, "TMP": workspace, "TEMP": workspace})
        return environment

    def _truncate(self, value: str | None) -> str:
        if not value:
            return ""
        raw = value.encode("utf-8", errors="replace")
        if len(raw) <= self.max_output_bytes:
            return raw.decode("utf-8", errors="replace")
        suffix = b"\n...[MORPHEUS OUTPUT TRUNCATED]"
        kept = raw[: max(0, self.max_output_bytes - len(suffix))] + suffix
        return kept.decode("utf-8", errors="replace")

    @staticmethod
    def _terminate(process: subprocess.Popen[str]) -> None:
        try:
            process.terminate()
            process.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
                process.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                pass

    @staticmethod
    def _view(job: _Job) -> dict[str, Any]:
        duration = None
        if job.started_monotonic is not None:
            end = job.finished_monotonic if job.finished_monotonic is not None else time.monotonic()
            duration = max(0.0, end - job.started_monotonic)
        return {
            "job_id": job.job_id,
            "kind": job.kind,
            "state": job.state.value,
            "returncode": job.returncode,
            "stdout": job.stdout,
            "stderr": job.stderr,
            "duration_seconds": duration,
            "workspace_deleted": job.workspace_deleted,
            "command_policy": "ALLOWLISTED_EXECUTABLE_NO_SHELL_TEMP_WORKSPACE",
            "evidence_state": (
                "LOCAL_BOUNDED_WORKER_COMPLETED"
                if job.state in {JobState.SUCCEEDED, JobState.FAILED, JobState.TIMED_OUT, JobState.CANCELLED}
                else "LOCAL_BOUNDED_WORKER_IN_PROGRESS"
            ),
            "truth_boundary": "Host-process isolation only; no container/VM/seccomp boundary is claimed.",
        }
