"""Exclusive private ownership receipts for one-shot container lifecycles."""

from __future__ import annotations

import json
import os
from pathlib import Path

from filelock import FileLock, SoftFileLock, Timeout

from py_docker.containers.models import ContainerIdentity, ContainerReservation
from py_docker.containers.service import Containers
from py_docker.errors import (
    CleanupUnconfirmedError,
    DockerOperationError,
    PendingReceiptError,
    ReceiptInUseError,
)


class ReceiptStore:
    """Serialize recovery and execution on a caller-owned private local path.

    Parameters
    ----------
    path : Path
        Receipt file within an existing private directory. This class does not
        create directories. Windows privacy depends on the directory's ACLs;
        POSIX files are created with mode 0600. The separate lock file may remain.
        One store belongs to one thread; other threads/processes use their own
        store instances and contend on the same native lock.
    """

    def __init__(self, path: Path) -> None:
        """Prepare a nonblocking native lock; do not read or change a receipt yet."""
        self._path = path.absolute()
        self._lock_path = self._path.with_name(self._path.name + ".lock")
        self._lock = FileLock(self._lock_path, timeout=0, mode=0o600)

    def __enter__(self) -> "ReceiptStore":
        """Acquire exclusive lifecycle ownership before any receipt or Docker access.

        Returns
        -------
        ReceiptStore
            This store with its native inter-process lock held.

        Raises
        ------
        ReceiptInUseError
            Another caller owns the receipt; this attempt changed nothing.
        DockerOperationError
            A symlink, unsupported lock backend or local filesystem error prevents use.
        """
        if (
            self._path.is_symlink()
            or self._lock_path.is_symlink()
            or isinstance(self._lock, SoftFileLock)
        ):
            raise DockerOperationError("open private container receipt")
        try:
            self._lock.acquire(timeout=0)
        except Timeout:
            raise ReceiptInUseError("acquire container receipt") from None
        except (OSError, NotImplementedError):
            raise DockerOperationError("lock private container receipt") from None
        return self

    def __exit__(self, *_: object) -> None:
        """Release the native lock without removing a potentially shared lock inode.

        Parameters
        ----------
        _ : tuple
            Context exception information; receipt cleanup is handled explicitly.
        """
        try:
            self._lock.release()
        except OSError:
            if _[0] is None:
                raise DockerOperationError(
                    "release private container receipt"
                ) from None

    def recover(self, containers: Containers) -> None:
        """Remove only a retained, observed owned container before clearing its receipt.

        Parameters
        ----------
        containers : Containers
            Scoped container service on the original selected Docker endpoint.

        Raises
        ------
        CleanupUnconfirmedError
            Corruption, conflict, daemon uncertainty or unobserved creation prevents
            cleanup. An immediately absent create could still arrive later; retain it.
        RuntimeError
            The caller did not acquire this store's lifecycle lock.
        """
        self._require_lock()
        if not self._path.exists():
            return
        try:
            value = json.loads(self._path.read_text(encoding="utf-8"))
            receipt = ContainerReservation.from_private_record(value)
        except (OSError, ValueError, TypeError):
            raise CleanupUnconfirmedError("read private container receipt") from None
        self.cleanup(containers, receipt)

    def save(self, reservation: ContainerReservation) -> None:
        """Flush ownership intent to an exclusive private file before a create request.

        Parameters
        ----------
        reservation : ContainerReservation
            Canonical private intent; secret conversion is confined to this file.

        Raises
        ------
        PendingReceiptError
            An existing receipt cannot be replaced; no create request was sent.
        DockerOperationError
            Ownership intent could not be written; no create request was sent.
        RuntimeError
            The lifecycle lock is not held.
        """
        self._require_lock()
        try:
            descriptor = os.open(
                self._path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            with os.fdopen(descriptor, "w", encoding="utf-8") as target:
                json.dump(reservation.to_private_record(), target)
                target.flush()
                os.fsync(target.fileno())
        except FileExistsError:
            raise PendingReceiptError("preserve pending container receipt") from None
        except OSError:
            raise DockerOperationError("write private container receipt") from None

    def discard_unstarted(self, reservation: ContainerReservation) -> None:
        """Clear only this intent after a typed failure proves creation did not happen.

        Parameters
        ----------
        reservation : ContainerReservation
            Exact private intent saved before a known pre-request failure or a
            definitive create rejection. Never use this for an uncertain request.

        Raises
        ------
        CleanupUnconfirmedError
            The file changed, cannot be read or cannot be removed. Keep the record
            and report the original safe failure through the primary attribute.
        RuntimeError
            The lifecycle lock is not held by this store in the current thread.
        """
        self._require_lock()
        try:
            stored = ContainerReservation.from_private_record(
                json.loads(self._path.read_text(encoding="utf-8"))
            )
            if stored != reservation:
                raise CleanupUnconfirmedError(
                    "verify unstarted container receipt", reservation
                )
            self._path.unlink()
        except Exception:
            raise CleanupUnconfirmedError(
                "clear unstarted container receipt", reservation
            ) from None

    def cleanup(
        self,
        containers: Containers,
        reservation: ContainerReservation,
        identity: ContainerIdentity | None = None,
    ) -> None:
        """Remove the observed immutable ID; uncertainty always retains the receipt.

        Parameters
        ----------
        containers : Containers
            Scoped container service on the selected daemon.
        reservation : ContainerReservation
            Pre-create ownership intent retained on every uncertain outcome.
        identity : ContainerIdentity or None
            Known created ID; None requires name-and-label reconciliation first.

        Raises
        ------
        CleanupUnconfirmedError
            The create remains unobserved, removal failed, or the receipt cannot
            be deleted. Cleanup uncertainty takes precedence over an earlier failure.
        RuntimeError
            The lifecycle lock is not held.
        """
        self._require_lock()
        try:
            owned = (
                identity if identity is not None else containers.reconcile(reservation)
            )
            if owned is None:
                raise CleanupUnconfirmedError(
                    "reconcile unobserved container creation", reservation
                )
            containers.remove(owned, force=True)
            self._path.unlink()
        except Exception:
            raise CleanupUnconfirmedError(
                "confirm owned container cleanup", reservation
            ) from None

    def _require_lock(self) -> None:
        """Reject direct store use outside its exclusive context.

        Raises
        ------
        RuntimeError
            This store does not hold its lifecycle lock in the current thread.
        """
        if not self._lock.is_locked:
            raise RuntimeError("Receipt store requires its exclusive lifecycle context")
