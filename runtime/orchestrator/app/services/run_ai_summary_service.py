"""Run AI summary generation and history management."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import UUID

from app.domain._base import utc_now
from app.domain.run import Run, RunStatus
from app.domain.run_ai_summary import RunAISummary, RunAISummaryType
from app.domain.task import Task
from app.repositories.run_ai_summary_repository import RunAISummaryRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository


class RunAISummaryError(ValueError):
    """Base service error for run AI summaries."""


class RunAISummaryRunNotFoundError(RunAISummaryError):
    """Raised when the target run cannot be found."""


@dataclass(slots=True, frozen=True)
class RunAISummaryContext:
    """Normalized source data used to build one run AI summary."""

    run: Run
    task: Task | None
    source_hash: str
    summary_markdown: str


class RunAISummaryService:
    """Generate, persist and list run AI summaries."""

    SOURCE_VERSION = "run.summary.v1"

    def __init__(
        self,
        *,
        run_repository: RunRepository,
        task_repository: TaskRepository,
        run_ai_summary_repository: RunAISummaryRepository,
    ) -> None:
        self.run_repository = run_repository
        self.task_repository = task_repository
        self.run_ai_summary_repository = run_ai_summary_repository

    def get_run_summary_history(self, *, run_id: UUID) -> list[RunAISummary]:
        """Return all stored AI summary snapshots for one run."""

        self._require_run(run_id=run_id)
        return self.run_ai_summary_repository.list_by_run_id(run_id)

    def generate_run_summary(
        self,
        *,
        run_id: UUID,
        regenerate: bool = False,
    ) -> RunAISummary:
        """Create a new run summary or reuse the current active snapshot."""

        context = self._build_context(run_id=run_id)
        active_summary = self.run_ai_summary_repository.get_active_by_run_id_and_type(
            run_id=run_id,
            summary_type=RunAISummaryType.RUN,
        )

        if (
            not regenerate
            and active_summary is not None
            and active_summary.source_hash == context.source_hash
        ):
            return active_summary

        if active_summary is not None:
            self.run_ai_summary_repository.mark_active_stale(
                run_id=run_id,
                summary_type=RunAISummaryType.RUN,
            )

        summary = RunAISummary(
            run_id=context.run.id,
            project_id=context.task.project_id if context.task is not None else None,
            task_id=context.run.task_id,
            deliverable_id=None,
            summary_type=RunAISummaryType.RUN,
            summary_markdown=context.summary_markdown,
            source_version=self.SOURCE_VERSION,
            source_hash=context.source_hash,
            generated_by_model=None,
            provider_receipt_id=None,
            generated_at=utc_now(),
            stale=False,
        )
        return self.run_ai_summary_repository.create(summary)

    def _build_context(self, *, run_id: UUID) -> RunAISummaryContext:
        """Resolve the source run and build deterministic summary inputs."""

        run = self._require_run(run_id=run_id)
        task = self.task_repository.get_by_id(run.task_id)
        source_payload = self._build_source_payload(run=run, task=task)
        source_hash = sha256(
            json.dumps(source_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        summary_markdown = self._build_summary_markdown(run=run, task=task)
        return RunAISummaryContext(
            run=run,
            task=task,
            source_hash=source_hash,
            summary_markdown=summary_markdown,
        )

    def _require_run(self, *, run_id: UUID) -> Run:
        """Return one run or raise a stable not-found error."""

        run = self.run_repository.get_by_id(run_id)
        if run is None:
            raise RunAISummaryRunNotFoundError(f"Run not found: {run_id}")

        return run

    def _build_source_payload(self, *, run: Run, task: Task | None) -> dict[str, object | None]:
        """Collect the deterministic fields that define one summary version."""

        return {
            "source_version": self.SOURCE_VERSION,
            "run_id": str(run.id),
            "task_id": str(run.task_id),
            "status": run.status.value,
            "model_name": run.model_name,
            "route_reason": run.route_reason,
            "result_summary": run.result_summary,
            "verification_summary": run.verification_summary,
            "failure_category": run.failure_category.value if run.failure_category else None,
            "quality_gate_passed": run.quality_gate_passed,
            "provider_key": run.provider_key,
            "prompt_template_key": run.prompt_template_key,
            "prompt_template_version": run.prompt_template_version,
            "prompt_char_count": run.prompt_char_count,
            "total_tokens": run.total_tokens,
            "estimated_cost": run.estimated_cost,
            "task_title": task.title if task is not None else None,
            "task_input_summary": task.input_summary if task is not None else None,
            "task_priority": task.priority.value if task is not None else None,
            "task_risk_level": task.risk_level.value if task is not None else None,
            "task_project_id": str(task.project_id) if task and task.project_id else None,
        }

    def _build_summary_markdown(self, *, run: Run, task: Task | None) -> str:
        """Build a concise Chinese markdown summary without invoking AI."""

        task_title = task.title if task is not None else "未记录"
        task_input = task.input_summary if task is not None else "未记录"
        completion_summary = self._compact_text(run.result_summary) or "本次运行没有单独记录结果摘要。"
        verification_summary = (
            self._compact_text(run.verification_summary)
            or "本次运行没有单独记录验证摘要。"
        )
        if run.status == RunStatus.SUCCEEDED:
            conclusion = "本次运行已成功完成。"
        elif run.status == RunStatus.FAILED:
            conclusion = "本次运行未成功完成，需要查看技术日志进一步排查。"
        elif run.status == RunStatus.CANCELLED:
            conclusion = "本次运行已取消。"
        else:
            conclusion = "本次运行仍处于进行中或待处理状态。"

        risk_line = "暂无明确风险。"
        if run.failure_category is not None:
            risk_line = f"检测到失败分类：{run.failure_category.value}。"
        elif run.quality_gate_passed is False:
            risk_line = "质量检查未通过，建议优先查看技术日志。"
        elif run.quality_gate_passed is None:
            risk_line = "当前没有记录质量检查结果。"

        next_step = "可继续查看交付件、审批或技术日志。"
        if run.status == RunStatus.FAILED:
            next_step = "建议优先查看失败原因和技术日志，再决定是否重试。"
        elif run.status == RunStatus.CANCELLED:
            next_step = "如需继续，请重新发起运行。"
        elif run.status == RunStatus.RUNNING:
            next_step = "运行尚未结束，可稍后刷新查看最新结果。"

        lines = [
            "## 一句话结论",
            conclusion,
            "",
            "## 本次完成内容",
            f"- 任务：{task_title}",
            f"- 任务输入：{task_input}",
            f"- 运行状态：{run.status.value}",
            f"- 执行摘要：{completion_summary}",
            f"- 验证摘要：{verification_summary}",
            "",
            "## 风险与注意事项",
            f"- {risk_line}",
            "",
            "## 下一步建议",
            f"- {next_step}",
        ]
        return "\n".join(lines).strip()

    @staticmethod
    def _compact_text(value: str | None) -> str | None:
        """Collapse one text snippet into a single readable line."""

        if value is None:
            return None

        normalized_value = " ".join(value.split())
        return normalized_value or None
