"""Worker bootstrap helpers (used by main in supervised mode)."""

from typing import Optional
from runtime.worker.worker_process import run_worker


def start_worker(profile: Optional[str], ipc_host: str, ipc_port: int) -> None:
    run_worker(profile=profile, ipc_host=ipc_host, ipc_port=ipc_port)


__all__ = ["start_worker"]
