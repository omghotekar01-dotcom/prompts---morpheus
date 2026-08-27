from __future__ import annotations

import sys
import time

from app.job_worker import LocalBoundedJobWorker


def _worker(*, timeout: float = 2.0, output: int = 4096) -> LocalBoundedJobWorker:
    return LocalBoundedJobWorker(
        allowed_executables=[sys.executable],
        max_workers=2,
        default_timeout_seconds=timeout,
        max_output_bytes=output,
    )


def test_worker_executes_allowlisted_process_without_shell_and_cleans_workspace() -> None:
    worker = _worker()
    try:
        submitted = worker.submit(
            kind="python-smoke",
            command=[sys.executable, "-c", "from pathlib import Path; print(Path('input.txt').read_text())"],
            files={"input.txt": "hello-worker"},
        )
        result = worker.wait(submitted["job_id"])
        assert result["state"] == "SUCCEEDED"
        assert "hello-worker" in result["stdout"]
        assert result["workspace_deleted"] is True
        assert result["command_policy"] == "ALLOWLISTED_EXECUTABLE_NO_SHELL_TEMP_WORKSPACE"
    finally:
        worker.shutdown()


def test_worker_rejects_path_escape_before_job_submission() -> None:
    worker = _worker()
    try:
        try:
            worker.submit(
                kind="escape",
                command=[sys.executable, "-c", "print('x')"],
                files={"../outside.txt": "no"},
            )
        except ValueError as exc:
            assert "relative" in str(exc) or ".." in str(exc)
        else:  # pragma: no cover
            raise AssertionError("path traversal input was accepted")
    finally:
        worker.shutdown()


def test_worker_times_out_long_running_process() -> None:
    worker = _worker(timeout=0.15)
    try:
        submitted = worker.submit(
            kind="timeout",
            command=[sys.executable, "-c", "import time; time.sleep(5)"],
        )
        result = worker.wait(submitted["job_id"], timeout_seconds=3)
        assert result["state"] == "TIMED_OUT"
        assert result["duration_seconds"] is not None
        assert result["duration_seconds"] < 3
    finally:
        worker.shutdown()


def test_worker_can_cancel_running_process() -> None:
    worker = _worker(timeout=5)
    try:
        submitted = worker.submit(
            kind="cancel",
            command=[sys.executable, "-c", "import time; print('started', flush=True); time.sleep(5)"],
        )
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and worker.get(submitted["job_id"])["state"] == "QUEUED":
            time.sleep(0.01)
        worker.cancel(submitted["job_id"])
        result = worker.wait(submitted["job_id"], timeout_seconds=3)
        assert result["state"] == "CANCELLED"
    finally:
        worker.shutdown()


def test_worker_truncates_large_output() -> None:
    worker = _worker(output=1024)
    try:
        submitted = worker.submit(
            kind="output-bound",
            command=[sys.executable, "-c", "print('x' * 5000)"],
        )
        result = worker.wait(submitted["job_id"])
        assert result["state"] == "SUCCEEDED"
        assert "MORPHEUS OUTPUT TRUNCATED" in result["stdout"]
        assert len(result["stdout"].encode("utf-8")) <= 1024
    finally:
        worker.shutdown()
