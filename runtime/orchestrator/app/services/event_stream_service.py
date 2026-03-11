"""In-process SSE event stream helpers for the Day 13 console."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import json
import threading
from typing import Any
from uuid import UUID, uuid4

from app.domain.run import Run, RunEventReason
from app.domain.task import Task, TaskEventReason, TaskStatus


@dataclass(slots=True, frozen=True)
class ConsoleStreamEvent:
    """A single event delivered to connected SSE clients."""

    id: str
    type: str
    timestamp: str
    payload: dict[str, Any]


@dataclass(slots=True)
class _Subscriber:
    """Internal subscriber state for one active SSE connection."""

    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[ConsoleStreamEvent]


class EventStreamService:
    """A tiny in-process pub/sub service for local single-process SSE."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[str, _Subscriber] = {}

    def subscribe(self) -> tuple[str, asyncio.Queue[ConsoleStreamEvent]]:
        """Register one SSE subscriber for the current event loop."""

        subscriber_id = str(uuid4())
        queue: asyncio.Queue[ConsoleStreamEvent] = asyncio.Queue(maxsize=200)
        subscriber = _Subscriber(
            loop=asyncio.get_running_loop(),
            queue=queue,
        )

        with self._lock:
            self._subscribers[subscriber_id] = subscriber

        return subscriber_id, queue

    def unsubscribe(self, subscriber_id: str) -> None:
        """Remove an SSE subscriber if it still exists."""

        with self._lock:
            self._subscribers.pop(subscriber_id, None)

    def build_event(self, event_type: str, payload: dict[str, Any]) -> ConsoleStreamEvent:
        """Create a timestamped stream event."""

        return ConsoleStreamEvent(
            id=str(uuid4()),
            type=event_type,
            timestamp=datetime.utcnow().isoformat() + "Z",
            payload=payload,
        )

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """Publish one event to all connected subscribers."""

        event = self.build_event(event_type, payload)

        with self._lock:
            subscribers = list(self._subscribers.items())

        stale_subscribers: list[str] = []
        for subscriber_id, subscriber in subscribers:
            try:
                subscriber.loop.call_soon_threadsafe(
                    self._push_to_queue,
                    subscriber.queue,
                    event,
                )
            except RuntimeError:
                stale_subscribers.append(subscriber_id)

        for subscriber_id in stale_subscribers:
            self.unsubscribe(subscriber_id)

    def publish_task_updated(
        self,
        *,
        task: Task,
        reason: TaskEventReason | str,
        previous_status: TaskStatus | str | None = None,
    ) -> None:
        """Publish a task change event."""

        payload: dict[str, Any] = {
            "reason": _normalize_enum_value(reason),
            "task": serialize_task(task),
        }
        if previous_status is not None:
            payload["previous_status"] = _normalize_enum_value(previous_status)

        self.publish("task_updated", payload)

    def publish_run_updated(
        self,
        *,
        run: Run,
        reason: RunEventReason | str,
    ) -> None:
        """Publish a run change event."""

        self.publish(
            "run_updated",
            {
                "reason": _normalize_enum_value(reason),
                "task_id": str(run.task_id),
                "run": serialize_run(run),
            },
        )

    def publish_log_event(
        self,
        *,
        task_id: str | None,
        run_id: str | None,
        log_path: str,
        record: dict[str, Any],
    ) -> None:
        """Publish a structured log event."""

        self.publish(
            "log_event",
            {
                "task_id": task_id,
                "run_id": run_id,
                "log_path": log_path,
                "record": record,
            },
        )

    @staticmethod
    def encode_sse(event: ConsoleStreamEvent) -> str:
        """Serialize one event to SSE wire format."""

        payload = {
            "id": event.id,
            "type": event.type,
            "timestamp": event.timestamp,
            "payload": event.payload,
        }
        data = json.dumps(payload, ensure_ascii=False, default=str)
        retry_line = ""
        retry_ms = event.payload.get("retry_ms")
        if isinstance(retry_ms, int) and retry_ms > 0:
            retry_line = f"retry: {retry_ms}\n"

        return f"id: {event.id}\nevent: {event.type}\n{retry_line}data: {data}\n\n"

    @staticmethod
    def _push_to_queue(
        queue: asyncio.Queue[ConsoleStreamEvent],
        event: ConsoleStreamEvent,
    ) -> None:
        """Best-effort push that drops the oldest event when the queue is full."""

        while queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        queue.put_nowait(event)


def serialize_task(task: Task) -> dict[str, Any]:
    """Convert a `Task` domain object into a console-friendly payload."""

    return {
        "id": str(task.id),
        "title": task.title,
        "status": task.status.value,
        "priority": task.priority.value,
        "input_summary": task.input_summary,
        "acceptance_criteria": task.acceptance_criteria,
        "depends_on_task_ids": [str(task_id) for task_id in task.depends_on_task_ids],
        "risk_level": task.risk_level.value,
        "human_status": task.human_status.value,
        "paused_reason": task.paused_reason,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


def serialize_run(run: Run) -> dict[str, Any]:
    """Convert a `Run` domain object into a console-friendly payload."""

    return {
        "id": str(run.id),
        "task_id": str(run.task_id),
        "status": run.status.value,
        "route_reason": run.route_reason,
        "routing_score": run.routing_score,
        "routing_score_breakdown": [
            item.model_dump() for item in run.routing_score_breakdown
        ],
        "result_summary": run.result_summary,
        "prompt_tokens": run.prompt_tokens,
        "completion_tokens": run.completion_tokens,
        "estimated_cost": run.estimated_cost,
        "log_path": run.log_path,
        "verification_mode": run.verification_mode,
        "verification_template": run.verification_template,
        "verification_command": run.verification_command,
        "verification_summary": run.verification_summary,
        "failure_category": run.failure_category.value if run.failure_category else None,
        "quality_gate_passed": run.quality_gate_passed,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "created_at": run.created_at.isoformat(),
    }


event_stream_service = EventStreamService()


def _normalize_enum_value(value: object) -> object:
    """Return the `.value` for enums while preserving plain values."""

    return getattr(value, "value", value)
