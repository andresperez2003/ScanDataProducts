"""Bloqueo por intentos fallidos: por usuario (CA-2.5) y por origen (CA-2.6), D-4."""

import math
from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.errors import TooManyAttemptsError
from src.models.domain import LoginAttemptData
from src.repos.login_attempt import LoginAttemptRepo

MAX_FAILURES_PER_USER = 5
MAX_FAILURES_PER_IP = 20
WINDOW = timedelta(minutes=15)
BLOCK = timedelta(minutes=15)
# Un bloqueo vigente empezó hace < BLOCK y su racha de fallos cabe en WINDOW.
_LOOKBACK = WINDOW + BLOCK


def blocked_until(
    attempts: Sequence[LoginAttemptData], *, max_failures: int
) -> datetime | None:
    """Fin del bloqueo más reciente que provocan estos intentos, o None.

    `attempts` va del más antiguo al más reciente. Solo cuentan los fallos
    consecutivos posteriores al último acceso correcto. Hay bloqueo cuando
    `max_failures` de ellos caben en WINDOW, y dura BLOCK desde el último de esos.
    """
    fallos: list[datetime] = []
    for intento in attempts:
        fallos = [] if intento.succeeded else [*fallos, intento.attempted_at]

    hasta: datetime | None = None
    for i in range(max_failures - 1, len(fallos)):
        if fallos[i] - fallos[i - max_failures + 1] < WINDOW:
            hasta = fallos[i] + BLOCK
    return hasta


async def ensure_not_blocked(
    db: AsyncSession, *, username_normalized: str, client_ip: str, now: datetime
) -> None:
    """Lanza TooManyAttemptsError si el usuario o el origen están bloqueados."""
    repo = LoginAttemptRepo(db)
    desde = now - _LOOKBACK
    finales = [
        blocked_until(
            await repo.recent_by_username(username_normalized, since=desde),
            max_failures=MAX_FAILURES_PER_USER,
        ),
        blocked_until(
            await repo.recent_by_ip(client_ip, since=desde),
            max_failures=MAX_FAILURES_PER_IP,
        ),
    ]
    vigentes = [fin for fin in finales if fin is not None and fin > now]
    if vigentes:
        espera = (max(vigentes) - now).total_seconds()
        raise TooManyAttemptsError(retry_after_seconds=math.ceil(espera))


async def record_attempt(
    db: AsyncSession,
    *,
    username_normalized: str,
    client_ip: str,
    succeeded: bool,
    now: datetime,
) -> None:
    """Registra un intento que llegó a comprobar credenciales. No confirma."""
    await LoginAttemptRepo(db).record(
        username_normalized=username_normalized,
        client_ip=client_ip,
        succeeded=succeeded,
        at=now,
    )
