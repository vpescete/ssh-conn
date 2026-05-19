"""Async TCP reachability check for SSH instances."""
from __future__ import annotations

import asyncio

from .store import SSHInstance

DEFAULT_TIMEOUT = 1.5

# Status values:
#   True  → connessione TCP riuscita (porta aperta)
#   False → connessione rifiutata o errore di rete
#   None  → timeout
Status = bool | None


async def _check_one(instance: SSHInstance, timeout: float) -> tuple[str, Status]:
    try:
        fut = asyncio.open_connection(instance.hostname, instance.port)
        reader, writer = await asyncio.wait_for(fut, timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001 — chiusura best-effort
            pass
        return instance.name, True
    except asyncio.TimeoutError:
        return instance.name, None
    except (OSError, ConnectionError):
        return instance.name, False


async def _check_all(
    instances: dict[str, SSHInstance], timeout: float
) -> dict[str, Status]:
    tasks = [_check_one(inst, timeout) for inst in instances.values()]
    pairs = await asyncio.gather(*tasks)
    return dict(pairs)


def check_reachability(
    instances: dict[str, SSHInstance], timeout: float = DEFAULT_TIMEOUT
) -> dict[str, Status]:
    if not instances:
        return {}
    return asyncio.run(_check_all(instances, timeout))
