"""Janitor — periodic cleanup of expired documents and assets.

Runs as an asyncio background task every 60 seconds.  On each tick it
enumerates expired records via ``FileStorage``, deletes them, and emits
audit events.
"""

from __future__ import annotations

import asyncio
import logging
import time

from app.core.audit import AuditLogger
from app.services.storage import FileStorage

logger = logging.getLogger("tte.janitor")


class Janitor:
    """Periodic cleanup of expired documents and assets.

    Usage::

        janitor = Janitor(storage, audit_logger)
        task = asyncio.create_task(janitor.run())
        # ...
        janitor.stop()
        await task
    """

    def __init__(
        self,
        storage: FileStorage,
        audit: AuditLogger,
        interval: float = 60.0,
    ) -> None:
        self._storage = storage
        self._audit = audit
        self._interval = interval
        self._stopped = asyncio.Event()

    async def run(self) -> None:
        """Main loop — runs until *stop* is called."""
        # Run an initial cleanup on startup.
        await self._cleanup_once()
        while not self._stopped.is_set():
            try:
                await asyncio.wait_for(
                    self._stopped.wait(), timeout=self._interval
                )
            except TimeoutError:
                await self._cleanup_once()

    def stop(self) -> None:
        """Signal the loop to exit."""
        self._stopped.set()

    async def _cleanup_once(self) -> None:
        """Delete all expired documents and assets."""
        try:
            await self._cleanup_documents()
        except Exception:
            logger.exception("Janitor: document cleanup failed")
        try:
            await self._cleanup_assets()
        except Exception:
            logger.exception("Janitor: asset cleanup failed")

    async def _cleanup_documents(self) -> None:
        """Delete expired documents in a thread executor."""
        loop = asyncio.get_running_loop()
        expired = await loop.run_in_executor(
            None, self._storage.list_expired_documents
        )
        for record in expired:
            try:
                await loop.run_in_executor(
                    None, self._storage.delete_document, record.id
                )
                self._audit.emit(
                    "document.expired",
                    doc_id=record.id,
                    filename=record.filename,
                    age_seconds=time.time() - record.created_at,
                )
                logger.info(
                    "Expired document deleted",
                    extra={"doc_id": record.id, "filename": record.filename},
                )
            except Exception:
                logger.exception(
                    "Failed to delete expired document",
                    extra={"doc_id": record.id},
                )

    async def _cleanup_assets(self) -> None:
        """Delete expired assets in a thread executor."""
        loop = asyncio.get_running_loop()
        expired = await loop.run_in_executor(
            None, self._storage.list_expired_assets
        )
        for record in expired:
            try:
                await loop.run_in_executor(
                    None, self._storage.delete_asset, record.id
                )
                self._audit.emit(
                    "asset.expired",
                    asset_id=record.id,
                    asset_type=record.type,
                    age_seconds=time.time() - record.created_at,
                )
                logger.info(
                    "Expired asset deleted",
                    extra={"asset_id": record.id, "type": record.type},
                )
            except Exception:
                logger.exception(
                    "Failed to delete expired asset",
                    extra={"asset_id": record.id},
                )
