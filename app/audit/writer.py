"""
Async Redis-Stream → PostgreSQL audit writer.

The writer runs as a background asyncio task (started on application startup).
It reads from the Redis Stream "upc:audit:stream", batches the records, and
bulk-inserts them into the audit PostgreSQL database every 500 ms or when
100 records have accumulated — whichever comes first.

Error handling:
- Redis read errors: logged; worker retries after a short sleep.
- DB insert errors: logged; the batch is dropped (records are already consumed
  from the stream to avoid endless retries that would block the stream).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

REDIS_STREAM_KEY = "upc:audit:stream"
CONSUMER_GROUP = "upc-audit-writers"
CONSUMER_NAME = "worker-1"
BATCH_SIZE = 100
FLUSH_INTERVAL_SECONDS = 0.5


def _parse_record(fields: dict[bytes | str, bytes | str]) -> dict[str, Any]:
    """Convert raw Redis stream fields (bytes or str) to a Python dict."""

    def _decode(v: bytes | str) -> str:
        return v.decode() if isinstance(v, bytes) else v

    def _decode_key(k: bytes | str) -> str:
        return k.decode() if isinstance(k, bytes) else k

    return {_decode_key(k): _decode(v) for k, v in fields.items()}


def _coerce_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Coerce string values from Redis into proper Python types for SQLAlchemy."""
    record: dict[str, Any] = {}

    record["id"] = raw.get("id") or str(uuid.uuid4())
    ts_str = raw.get("timestamp_utc", "")
    try:
        record["timestamp_utc"] = datetime.fromisoformat(ts_str) if ts_str else datetime.now(timezone.utc)
    except ValueError:
        record["timestamp_utc"] = datetime.now(timezone.utc)

    record["client_id"] = raw.get("client_id", "unknown")[:100]
    record["user_sub"] = raw.get("user_sub") or None
    record["method"] = raw.get("method", "GET")[:10]
    record["endpoint"] = raw.get("endpoint", "/")[:500]

    qp_raw = raw.get("query_params", "")
    try:
        record["query_params"] = json.loads(qp_raw) if qp_raw else None
    except (ValueError, TypeError):
        record["query_params"] = None

    record["request_body_hash"] = raw.get("request_body_hash") or None
    scopes_raw = raw.get("scopes_used", "[]")
    try:
        record["scopes_used"] = json.loads(scopes_raw) if scopes_raw else []
    except (ValueError, TypeError):
        record["scopes_used"] = []

    record["ip_origin"] = raw.get("ip_origin", "0.0.0.0")
    record["user_agent"] = (raw.get("user_agent") or None)
    if record["user_agent"]:
        record["user_agent"] = record["user_agent"][:500]

    try:
        record["http_status"] = int(raw.get("http_status", 0))
    except (ValueError, TypeError):
        record["http_status"] = 0

    try:
        record["response_time_ms"] = int(raw.get("response_time_ms", 0))
    except (ValueError, TypeError):
        record["response_time_ms"] = 0

    record["error_code"] = raw.get("error_code") or None
    record["error_message"] = raw.get("error_message") or None

    rr = raw.get("records_returned")
    try:
        record["records_returned"] = int(rr) if rr else None
    except (ValueError, TypeError):
        record["records_returned"] = None

    jti = raw.get("token_jti", "")
    try:
        record["token_jti"] = uuid.UUID(jti) if jti else None
    except (ValueError, AttributeError):
        record["token_jti"] = None

    record["geo_country"] = raw.get("geo_country") or None
    record["geo_city"] = raw.get("geo_city") or None
    flagged_raw = raw.get("flagged", "false")
    record["flagged"] = flagged_raw in ("true", "True", "1", True)
    record["flag_reason"] = raw.get("flag_reason") or None

    return record


INSERT_SQL = text(
    """
    INSERT INTO api_audit_log (
        id, timestamp_utc, client_id, user_sub, method, endpoint,
        query_params, request_body_hash, scopes_used, ip_origin,
        user_agent, http_status, response_time_ms, error_code,
        error_message, records_returned, token_jti, geo_country,
        geo_city, flagged, flag_reason
    ) VALUES (
        :id, :timestamp_utc, :client_id, :user_sub, :method, :endpoint,
        :query_params, :request_body_hash, :scopes_used, :ip_origin,
        :user_agent, :http_status, :response_time_ms, :error_code,
        :error_message, :records_returned, :token_jti, :geo_country,
        :geo_city, :flagged, :flag_reason
    )
    ON CONFLICT (id) DO NOTHING
    """
)


async def _flush_batch(
    batch: list[dict[str, Any]],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if not batch:
        return
    async with session_factory() as session:
        try:
            for record in batch:
                await session.execute(INSERT_SQL, record)
            await session.commit()
            logger.debug("Audit writer flushed %d record(s) to DB", len(batch))
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            logger.error("Audit writer DB insert failed, batch dropped: %s", exc)


async def audit_writer_task(
    redis_client: Any,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """
    Long-running background task.  Reads from the Redis Stream and
    bulk-inserts into the audit database.
    """
    # Ensure consumer group exists
    try:
        await redis_client.xgroup_create(
            REDIS_STREAM_KEY, CONSUMER_GROUP, id="0", mkstream=True
        )
        logger.info("Audit writer: consumer group '%s' created", CONSUMER_GROUP)
    except Exception as exc:  # noqa: BLE001
        # BUSYGROUP means the group already exists — not an error.
        if "BUSYGROUP" not in str(exc):
            logger.warning("Audit writer: xgroup_create warning: %s", exc)

    batch: list[dict[str, Any]] = []
    last_flush = asyncio.get_event_loop().time()

    while True:
        try:
            messages = await redis_client.xreadgroup(
                CONSUMER_GROUP,
                CONSUMER_NAME,
                {REDIS_STREAM_KEY: ">"},
                count=BATCH_SIZE,
                block=int(FLUSH_INTERVAL_SECONDS * 1000),
            )
        except asyncio.CancelledError:
            # Graceful shutdown — flush whatever is in the buffer.
            if batch:
                await _flush_batch(batch, session_factory)
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("Audit writer: Redis read error: %s", exc)
            await asyncio.sleep(1.0)
            continue

        if messages:
            for _stream, entries in messages:
                for msg_id, fields in entries:
                    raw = _parse_record(fields)
                    record = _coerce_record(raw)
                    batch.append(record)

                    # Acknowledge immediately so the message is not redelivered.
                    try:
                        await redis_client.xack(REDIS_STREAM_KEY, CONSUMER_GROUP, msg_id)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Audit writer: xack failed: %s", exc)

        now = asyncio.get_event_loop().time()
        if len(batch) >= BATCH_SIZE or (batch and (now - last_flush) >= FLUSH_INTERVAL_SECONDS):
            await _flush_batch(batch, session_factory)
            batch = []
            last_flush = now
        else:
            # Small sleep to yield to other tasks when stream is empty.
            await asyncio.sleep(0.05)
