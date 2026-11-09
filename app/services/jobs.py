"""Background jobs with progress steps stored in SQLite, so the browser can poll long AI/network work."""

import logging
import traceback
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app import repo
from app.config import Settings
from app.db import session

log = logging.getLogger(__name__)


class JobContext:
    def __init__(self, job_id: str, settings: Settings):
        self.job_id = job_id
        self.settings = settings
        self.steps: list[dict] = []

    def step(self, label: str) -> None:
        if self.steps and self.steps[-1]["state"] == "running":
            self.steps[-1]["state"] = "done"
        self.steps.append({"label": label, "state": "running", "note": ""})
        self._save()

    def note(self, text: str) -> None:
        if self.steps:
            self.steps[-1]["note"] = text
            self._save()

    def warn(self, text: str) -> None:
        log.warning("job %s: %s", self.job_id, text)
        if self.steps:
            self.steps[-1]["state"] = "warning"
            self.steps[-1]["note"] = text
            self._save()

    def set_site(self, site_id: int) -> None:
        with session(self.settings.db_path) as conn:
            repo.update_job(conn, self.job_id, site_id=site_id)

    def _save(self) -> None:
        with session(self.settings.db_path) as conn:
            repo.update_job(conn, self.job_id, steps=self.steps)

    def finish_steps(self) -> None:
        for step in self.steps:
            if step["state"] == "running":
                step["state"] = "done"


JobFn = Callable[[JobContext], dict[str, Any] | None]


class JobRunner:
    def __init__(self, settings: Settings, max_workers: int = 2, synchronous: bool = False):
        self.settings = settings
        self.synchronous = synchronous  # tests run jobs inline
        self._executor = None if synchronous else ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="job")

    def submit(self, kind: str, fn: JobFn, *, site_id: int | None = None, input_data: dict | None = None) -> str:
        job_id = uuid.uuid4().hex
        with session(self.settings.db_path) as conn:
            repo.insert_job(conn, job_id, kind, site_id, input_data or {})
        if self.synchronous:
            self._run(job_id, fn)
        else:
            self._executor.submit(self._run, job_id, fn)  # type: ignore[union-attr]
        return job_id

    def _run(self, job_id: str, fn: JobFn) -> None:
        ctx = JobContext(job_id, self.settings)
        with session(self.settings.db_path) as conn:
            repo.update_job(conn, job_id, status="running")
        try:
            result = fn(ctx) or {}
            ctx.finish_steps()
            with session(self.settings.db_path) as conn:
                repo.update_job(conn, job_id, status="done", steps=ctx.steps, result=result)
        except Exception as exc:  # noqa: BLE001 - job failures are reported to the user, not raised
            log.error("job %s failed: %s\n%s", job_id, exc, traceback.format_exc())
            if ctx.steps and ctx.steps[-1]["state"] == "running":
                ctx.steps[-1]["state"] = "failed"
            with session(self.settings.db_path) as conn:
                repo.update_job(conn, job_id, status="failed", steps=ctx.steps, error=str(exc)[:1000])

    def shutdown(self) -> None:
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
