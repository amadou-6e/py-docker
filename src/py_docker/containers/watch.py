"""Observe and clean exact reservations, including delayed creation after loss."""

import math
import time
from typing import TYPE_CHECKING

from py_docker.containers.models import CleanupResult, ContainerReservation
from py_docker.errors import DockerOperationError, OwnershipConflictError

if TYPE_CHECKING:
    from py_docker.containers.service import Containers


class ContainerWatch:
    """Scope every observation to one client's endpoint and expected labels.

    Parameters
    ----------
    containers : Containers
        Caller-owned operations on the original selected endpoint.
    reservation : ContainerReservation
        Exact name and private ownership labels, recorded before creation.
    """

    def __init__(self, containers: "Containers", reservation: ContainerReservation):
        """Retain scoped operations without opening or changing a connection."""
        self._containers = containers
        self._reservation = reservation

    def inspect(self) -> tuple[str, str | None]:
        """Return safe absent/owned/conflict/unknown state and observed ID.

        Returns
        -------
        tuple
            State and immutable ID; absence does not resolve an unknown create.
        """
        try:
            identity = self._containers.reconcile(self._reservation)
            return ("owned", identity.id) if identity is not None else ("absent", None)
        except OwnershipConflictError:
            return "conflict", None
        except DockerOperationError:
            return "unknown", None

    def cleanup(self, *, watch_seconds: float = 0) -> CleanupResult:
        """Remove owned immutable IDs and optionally watch for delayed creation.

        Parameters
        ----------
        watch_seconds : float
            Nonnegative finite observation window after client loss. An entirely
            absent watch is unverified because an outstanding create may arrive.

        Returns
        -------
        CleanupResult
            Exact cleanup result. A zero window is for an already reconciled
            operation; it must not be used to resolve an unknown create request.

        Raises
        ------
        ValueError
            The requested observation duration is negative or nonfinite.
        """
        if not math.isfinite(watch_seconds) or watch_seconds < 0:
            raise ValueError("A finite nonnegative observation window is required")
        deadline = time.monotonic() + watch_seconds
        observed = False
        while True:
            try:
                identity = self._containers.reconcile(self._reservation)
                if identity is not None:
                    self._containers.remove(identity, force=True)
                    observed = True
            except OwnershipConflictError:
                return CleanupResult(verified=False, detail="conflict")
            except DockerOperationError:
                return CleanupResult(verified=False, detail="unknown")
            if time.monotonic() >= deadline:
                state, _ = self.inspect()
                verified = state == "absent" and (observed or watch_seconds == 0)
                detail = (
                    ("removed_after_loss" if watch_seconds else "removed")
                    if observed
                    else "never_observed"
                    if watch_seconds and state == "absent"
                    else state
                )
                return CleanupResult(verified=verified, detail=detail)
            time.sleep(min(0.1, max(0, deadline - time.monotonic())))
