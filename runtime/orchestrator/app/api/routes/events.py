"""SSE endpoints shared by the console and Day08 role workbench."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.services.event_stream_service import event_stream_service


_HEARTBEAT_INTERVAL_SECONDS = 10


router = APIRouter(prefix="/events", tags=["events"])


@router.get(
    "/console",
    summary="订阅控制台实时事件流",
)
async def stream_console_events(request: Request) -> StreamingResponse:
    """Stream Day 13 console events over SSE."""

    subscriber_id, queue = event_stream_service.subscribe()

    async def event_generator():
        try:
            connected_event = event_stream_service.build_event(
                "connected",
                {
                    "message": "Console SSE stream connected.",
                    "retry_ms": 3000,
                },
            )
            yield event_stream_service.encode_sse(connected_event)

            while True:
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(
                        queue.get(),
                        timeout=_HEARTBEAT_INTERVAL_SECONDS,
                    )
                except TimeoutError:
                    heartbeat_event = event_stream_service.build_event(
                        "heartbeat",
                        {"message": "Console SSE heartbeat."},
                    )
                    yield event_stream_service.encode_sse(heartbeat_event)
                    continue

                yield event_stream_service.encode_sse(event)
        finally:
            event_stream_service.unsubscribe(subscriber_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
