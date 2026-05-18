"""Run AI summary generation and history management."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import logging
from typing import Callable
from uuid import UUID

from app.domain.run import Run, RunStatus
from app.domain.run_ai_summary import (
    RunAISummary,
    RunAISummarySource,
    RunAISummaryStatus,
    RunAISummaryType,
)
from app.domain.task import Task
from app.domain._base import utc_now
from app.repositories.run_ai_summary_repository import RunAISummaryRepository
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository

logger = logging.getLogger(__name__)

# ── Markdown validation constants ─────────────────────────────────

_REQUIRED_HEADINGS = [
    "## 运行结论",
    "## 已完成内容",
    "## 风险与注意事项",
    "## 下一步建议",
    "## 技术依据",
]

_MAX_MARKDOWN_LENGTH = 8_000

# Type alias for a callable that generates summary text via a provider.
AISummaryTextGenerator = Callable[
    [str, str, str],  # model_name, prompt_text, request_id
    tuple[str, str | None],  # (output_text, provider_receipt_id | None)
]


class RunAISummaryError(ValueError):
    """Base service error for run AI summaries."""


class RunAISummaryRunNotFoundError(RunAISummaryError):
    """Raised when the target run cannot be found."""


@dataclass(slots=True, frozen=True)
class RunAISummaryContext:
    """Normalized source data used to build one run AI summary."""

    run: Run
    task: Task | None
    source_fingerprint: str
    prompt_text: str
    prompt_hash: str
    ai_prompt_hash: str
    summary_markdown: str


class RunAISummaryService:
    """Generate, persist and list run AI summaries."""

    SOURCE_VERSION = "run.summary.v2"
    SUMMARY_SOURCE = RunAISummarySource.RULE_FALLBACK
    SUMMARY_STATUS = RunAISummaryStatus.SUCCEEDED
    SUMMARY_MODEL_PROVIDER = "local_rule_engine"
    SUMMARY_MODEL_NAME = "run_summary.rule_fallback.v2"

    def __init__(
        self,
        *,
        run_repository: RunRepository,
        task_repository: TaskRepository,
        run_ai_summary_repository: RunAISummaryRepository,
        provider_config_service: object | None = None,
        ai_text_generator: AISummaryTextGenerator | None = None,
    ) -> None:
        self.run_repository = run_repository
        self.task_repository = task_repository
        self.run_ai_summary_repository = run_ai_summary_repository
        self._provider_config_service = provider_config_service
        self._ai_text_generator = ai_text_generator
        self._last_ai_error: str | None = None

    # ── Singular current-summary helpers ──────────────────────────

    def get_active_summary(self, *, run_id: UUID) -> RunAISummary | None:
        """Return the current active RUN-type summary or None."""

        self._require_run(run_id=run_id)
        return self.run_ai_summary_repository.get_active_by_run_id(run_id)

    def generate_current_summary(
        self,
        *,
        run_id: UUID,
    ) -> RunAISummary:
        """Create or reuse the active summary (singular entry point)."""

        return self.generate_run_summary(run_id=run_id, regenerate=False)

    def regenerate_current_summary(
        self,
        *,
        run_id: UUID,
    ) -> RunAISummary:
        """Force a new active summary, marking the prior one stale."""

        return self.generate_run_summary(run_id=run_id, regenerate=True)

    # ── History / plural helpers (kept for debug) ──────────────────

    def get_run_summary_history(self, *, run_id: UUID) -> list[RunAISummary]:
        """Return all stored AI summary snapshots for one run."""

        self._require_run(run_id=run_id)
        return self.run_ai_summary_repository.list_by_run_id(run_id)

    # ── Core generation ────────────────────────────────────────────

    def generate_run_summary(
        self,
        *,
        run_id: UUID,
        regenerate: bool = False,
    ) -> RunAISummary:
        """Create a new run summary or reuse the current active snapshot.

        Priority:
        1. If provider is configured → attempt real AI generation.
        2. If AI succeeds with valid markdown → save as source=ai.
        3. If AI fails / times out / returns invalid markdown → fallback
           to rule_fallback with a short error_summary.
        4. If provider is not configured → rule_fallback directly.
        """

        context = self._build_context(run_id=run_id)
        active_summary = self.run_ai_summary_repository.get_active_by_run_id_and_type(
            run_id=run_id,
            summary_type=RunAISummaryType.RUN,
        )

        can_try_ai = self._can_try_ai()

        # Determine the expected source for reuse checks.
        expected_source = RunAISummarySource.AI if can_try_ai else RunAISummarySource.RULE_FALLBACK
        expected_prompt_hash = (
            context.ai_prompt_hash if can_try_ai else context.prompt_hash
        )

        # ── Reuse check ────────────────────────────────────────
        if (
            not regenerate
            and active_summary is not None
            and active_summary.status == RunAISummaryStatus.SUCCEEDED
            and active_summary.source == expected_source
            and active_summary.source_fingerprint == context.source_fingerprint
            and active_summary.prompt_hash == expected_prompt_hash
        ):
            return active_summary

        # ── Mark old active stale ──────────────────────────────
        if active_summary is not None:
            self.run_ai_summary_repository.mark_active_stale(
                run_id=run_id,
                summary_type=RunAISummaryType.RUN,
            )

        # ── Try AI generation ──────────────────────────────────
        if can_try_ai:
            ai_result = self._try_ai_summary(context=context)
            if ai_result is not None:
                return ai_result
            # AI failed → fall through to rule_fallback with error_summary set.
            error_reason = self._last_ai_error or "AI 摘要生成失败，已使用规则回退"
        else:
            error_reason = None

        # ── Rule fallback ──────────────────────────────────────
        return self._create_rule_fallback_summary(
            context=context,
            error_summary=error_reason,
        )

    def _build_context(self, *, run_id: UUID) -> RunAISummaryContext:
        """Resolve the source run and build deterministic summary inputs."""

        run = self._require_run(run_id=run_id)
        task = self.task_repository.get_by_id(run.task_id)
        source_payload = self._build_source_payload(run=run, task=task)
        source_fingerprint = sha256(
            json.dumps(source_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        prompt_text = self._build_prompt_text(
            run=run,
            task=task,
            source_fingerprint=source_fingerprint,
        )
        prompt_hash = sha256(prompt_text.encode("utf-8")).hexdigest()
        summary_markdown = self._build_summary_markdown(
            run=run,
            task=task,
            source_fingerprint=source_fingerprint,
            prompt_hash=prompt_hash,
        )
        # Pre-compute AI prompt hash so source=ai and reuse checks can use it
        ai_prompt_text = self._build_ai_prompt_text_direct(
            run=run,
            task=task,
        )
        ai_prompt_hash = sha256(ai_prompt_text.encode("utf-8")).hexdigest()
        return RunAISummaryContext(
            run=run,
            task=task,
            source_fingerprint=source_fingerprint,
            prompt_text=prompt_text,
            prompt_hash=prompt_hash,
            ai_prompt_hash=ai_prompt_hash,
            summary_markdown=summary_markdown,
        )

    def _require_run(self, *, run_id: UUID) -> Run:
        """Return one run or raise a stable not-found error."""

        run = self.run_repository.get_by_id(run_id)
        if run is None:
            raise RunAISummaryRunNotFoundError(f"Run not found: {run_id}")

        return run

    def _build_source_payload(
        self,
        *,
        run: Run,
        task: Task | None,
    ) -> dict[str, object | None]:
        """Collect the deterministic fields that define one summary version."""

        return {
            "source_version": self.SOURCE_VERSION,
            "run_id": str(run.id),
            "task_id": str(run.task_id),
            "project_id": str(task.project_id) if task and task.project_id else None,
            "task_title": task.title if task is not None else None,
            "task_input_summary": task.input_summary if task is not None else None,
            "task_priority": task.priority.value if task is not None else None,
            "task_risk_level": task.risk_level.value if task is not None else None,
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
        }

    def _build_prompt_text(
        self,
        *,
        run: Run,
        task: Task | None,
        source_fingerprint: str,
    ) -> str:
        """Build the canonical prompt text used to derive the prompt hash."""

        task_title = task.title if task is not None else "未记录"
        task_input = task.input_summary if task is not None else "未记录"
        lines = [
            "你是 AI 运行摘要生成器，只输出中文 Markdown。",
            "请使用固定五个标题：",
            "## 运行结论",
            "## 已完成内容",
            "## 风险与注意事项",
            "## 下一步建议",
            "## 技术依据",
            "",
            "源数据：",
            f"- 运行 ID：{run.id}",
            f"- 任务标题：{task_title}",
            f"- 任务输入：{task_input}",
            f"- 运行状态：{run.status.value}",
            f"- 来源指纹：{source_fingerprint}",
            f"- 结果摘要：{run.result_summary or '未记录'}",
            f"- 验证摘要：{run.verification_summary or '未记录'}",
        ]
        return "\n".join(lines).strip()

    def _build_summary_markdown(
        self,
        *,
        run: Run,
        task: Task | None,
        source_fingerprint: str,
        prompt_hash: str,
    ) -> str:
        """Build a concise Chinese markdown summary without invoking AI."""

        task_title = task.title if task is not None else "未记录"
        task_input = task.input_summary if task is not None else "未记录"
        completion_summary = self._compact_text(run.result_summary) or "本次运行没有单独记录结果摘要。"
        verification_summary = (
            self._compact_text(run.verification_summary)
            or "本次运行没有单独记录验证摘要。"
        )

        if run.status == RunStatus.SUCCEEDED:
            conclusion = "本次运行已成功完成，摘要已按规则回退生成。"
        elif run.status == RunStatus.FAILED:
            conclusion = "本次运行未成功完成，但摘要仍可帮助定位问题。"
        elif run.status == RunStatus.CANCELLED:
            conclusion = "本次运行已取消。"
        else:
            conclusion = "本次运行仍处于进行中或待处理状态。"

        if run.failure_category is not None:
            risk_line = f"检测到失败分类：{run.failure_category.value}。"
        elif run.quality_gate_passed is False:
            risk_line = "质量检查未通过，建议优先查看技术日志。"
        elif run.quality_gate_passed is None:
            risk_line = "当前没有记录质量检查结果。"
        else:
            risk_line = "当前没有额外风险信号。"

        if run.status == RunStatus.FAILED:
            next_step = "建议优先查看失败原因和技术日志，再决定是否重试。"
        elif run.status == RunStatus.CANCELLED:
            next_step = "如需继续，请重新发起运行。"
        elif run.status == RunStatus.RUNNING:
            next_step = "运行尚未结束，可稍后刷新查看最新结果。"
        else:
            next_step = "可继续查看交付件、审批或技术日志。"

        # ── 技术依据 ──────────────────────────────────────────
        provider_label = run.provider_key or "未记录"
        model_label = run.model_name or "未记录"
        receipt_label = run.provider_receipt_id or "未记录"

        lines = [
            "## 运行结论",
            conclusion,
            "",
            "## 已完成内容",
            f"- 任务：{task_title}",
            f"- 任务输入：{task_input}",
            f"- 运行状态：{run.status.value}",
            f"- 摘要来源：规则回退",
            f"- 模型服务：{self.SUMMARY_MODEL_PROVIDER} / {self.SUMMARY_MODEL_NAME}",
            "",
            "## 风险与注意事项",
            f"- {risk_line}",
            "",
            "## 下一步建议",
            f"- {next_step}",
            "",
            "## 技术依据",
            f"- 运行状态：{run.status.value}",
            f"- 结果摘要：{completion_summary}",
            f"- 验证摘要：{verification_summary}",
            f"- 质量检查：{'通过' if run.quality_gate_passed is True else ('拦截' if run.quality_gate_passed is False else '未记录')}",
            f"- 模型服务 Key：{provider_label}",
            f"- 模型名称：{model_label}",
            f"- 模型回执 ID：{receipt_label}",
            f"- 摘要依据：运行状态、结果摘要、验证摘要、质量检查、模型服务记录",
            f"- 调试指纹：已记录，可在前端状态条或技术日志中查看完整值",
        ]
        return "\n".join(lines).strip()

    # ── AI generation helpers ──────────────────────────────────────

    def _can_try_ai(self) -> bool:
        """Check whether real AI summary generation is possible."""

        # Test-injectable fake generator always wins.
        if self._ai_text_generator is not None:
            return True

        if self._provider_config_service is None:
            return False
        try:
            runtime_config = self._provider_config_service.resolve_openai_runtime_config()
        except Exception:
            return False
        return bool(runtime_config.api_key)

    def _try_ai_summary(self, *, context: RunAISummaryContext) -> RunAISummary | None:
        """Attempt real AI summary generation. Returns None on any failure."""

        self._last_ai_error = None

        request_id = str(context.run.id)
        ai_prompt = self._build_ai_prompt_text(context=context)

        # Resolve config: test-injected generator vs. real provider config
        if self._ai_text_generator is not None:
            model_name = "test_model"
            provider_type = "openai_compatible"
            try:
                output_text, receipt_id = self._ai_text_generator(
                    model_name, ai_prompt, request_id
                )
            except Exception as exc:
                category = getattr(exc, "category", "unknown")
                brief = str(exc)[:200]
                self._last_ai_error = f"真实 AI 摘要生成失败，已使用规则回退：{category}"
                logger.warning("run_ai_summary: AI fake-generator failed [%s]: %s", category, brief)
                return None
        else:
            try:
                runtime_config = self._provider_config_service.resolve_openai_runtime_config()
            except Exception as exc:
                self._last_ai_error = f"无法读取 Provider 配置：{exc}"
                logger.warning("run_ai_summary: cannot read provider config: %s", exc)
                return None

            model_name = runtime_config.model_names.get("balanced", "gpt-4.1-mini")
            provider_type = runtime_config.detected_provider_type

            try:
                output_text, receipt_id = self._call_provider_text(
                    runtime_config=runtime_config,
                    model_name=model_name,
                    prompt_text=ai_prompt,
                    request_id=request_id,
                )
            except Exception as exc:
                category = getattr(exc, "category", "unknown")
                brief = str(exc)[:200]
                self._last_ai_error = f"真实 AI 摘要生成失败，已使用规则回退：{category}"
                logger.warning("run_ai_summary: AI generation failed [%s]: %s", category, brief)
                return None

        # Validate the AI output
        validation_error = self._validate_ai_summary_markdown(output_text)
        if validation_error is not None:
            self._last_ai_error = f"AI 摘要格式不符合要求，已使用规则回退：{validation_error}"
            logger.warning("run_ai_summary: markdown validation failed: %s", validation_error)
            return None

        # Truncate if needed
        if len(output_text) > _MAX_MARKDOWN_LENGTH:
            output_text = output_text[:_MAX_MARKDOWN_LENGTH]

        # Save source=ai summary
        now = utc_now()
        summary = RunAISummary(
            run_id=context.run.id,
            project_id=context.task.project_id if context.task is not None else None,
            task_id=context.run.task_id,
            deliverable_id=None,
            summary_type=RunAISummaryType.RUN,
            status=RunAISummaryStatus.SUCCEEDED,
            source=RunAISummarySource.AI,
            summary_markdown=output_text,
            source_version=self.SOURCE_VERSION,
            source_fingerprint=context.source_fingerprint,
            source_hash=context.source_fingerprint,
            model_provider=provider_type,
            model_name=model_name,
            prompt_hash=context.ai_prompt_hash,
            provider_receipt_id=receipt_id,
            generated_at=now,
            created_at=now,
            updated_at=now,
            error_summary=None,
            stale=False,
        )
        return self.run_ai_summary_repository.create(summary)

    def _build_ai_prompt_text_direct(
        self,
        *,
        run: Run,
        task: Task | None,
    ) -> str:
        """Build the AI prompt text without requiring a RunAISummaryContext."""

        task_title = task.title if task is not None else "未记录"
        task_input = task.input_summary if task is not None else "未记录"
        provider_label = run.provider_key or "未记录"
        model_label = run.model_name or "未记录"
        receipt_label = run.provider_receipt_id or "未记录"
        quality_label = (
            "通过" if run.quality_gate_passed is True
            else ("拦截" if run.quality_gate_passed is False else "未记录")
        )

        lines = [
            "你是 AI 运行摘要生成器。只输出中文 Markdown，严格使用以下五个标题，不得增减：",
            "",
            "## 运行结论",
            "## 已完成内容",
            "## 风险与注意事项",
            "## 下一步建议",
            "## 技术依据",
            "",
            "要求：",
            "- 不输出 JSON。",
            "- 不用 ``` 代码块包裹全文。",
            "- 不编造未在源数据中出现的事实。",
            '- 区分「原始任务运行的 provider 执行结果」和「摘要生成来源」。',
            "- 不在正文里输出完整 source_fingerprint / prompt_hash。",
            "- 技术依据可引用运行状态、结果摘要、验证摘要、质量检查、模型服务 Key、模型名称、模型回执 ID。",
            "- 内容简洁，面向后台用户。",
            "",
            "源数据：",
            f"- 运行 ID：{run.id}",
            f"- 任务标题：{task_title}",
            f"- 任务输入：{task_input}",
            f"- 运行状态：{run.status.value}",
            f"- 结果摘要：{run.result_summary or '未记录'}",
            f"- 验证摘要：{run.verification_summary or '未记录'}",
            f"- 质量检查：{quality_label}",
            f"- 模型服务 Key：{provider_label}",
            f"- 模型名称：{model_label}",
            f"- 模型回执 ID：{receipt_label}",
        ]
        if run.failure_category is not None:
            lines.append(f"- 失败分类：{run.failure_category.value}")
        return "\n".join(lines).strip()

    def _build_ai_prompt_text(self, *, context: RunAISummaryContext) -> str:
        """Build the AI prompt text from a context (for use during generation)."""

        return self._build_ai_prompt_text_direct(
            run=context.run,
            task=context.task,
        )

    def _call_provider_text(
        self,
        *,
        runtime_config: object,
        model_name: str,
        prompt_text: str,
        request_id: str,
    ) -> tuple[str, str | None]:
        """Invoke the real provider to generate summary text.

        Returns (output_text, provider_receipt_id).
        """

        from app.services.openai_provider_executor_service import (
            OpenAIProviderExecutorService,
        )

        executor = OpenAIProviderExecutorService(
            api_key=runtime_config.api_key,
            base_url=runtime_config.base_url,
            timeout_seconds=runtime_config.timeout_seconds,
        )
        response = executor.generate_text(
            model_name=model_name,
            prompt_text=prompt_text,
            request_id=request_id,
            prompt_key="run_ai_summary",
            provider_key=runtime_config.detected_provider_type,
        )
        receipt_id = None
        if response.provider_usage_receipt is not None:
            receipt_id = response.provider_usage_receipt.receipt_id
        output_text = response.output_text or response.summary
        return output_text, receipt_id

    def _create_rule_fallback_summary(
        self,
        *,
        context: RunAISummaryContext,
        error_summary: str | None,
    ) -> RunAISummary:
        """Create and persist a rule_fallback summary."""

        now = utc_now()
        summary = RunAISummary(
            run_id=context.run.id,
            project_id=context.task.project_id if context.task is not None else None,
            task_id=context.run.task_id,
            deliverable_id=None,
            summary_type=RunAISummaryType.RUN,
            status=RunAISummaryStatus.SUCCEEDED,
            source=RunAISummarySource.RULE_FALLBACK,
            summary_markdown=context.summary_markdown,
            source_version=self.SOURCE_VERSION,
            source_fingerprint=context.source_fingerprint,
            source_hash=context.source_fingerprint,
            model_provider=self.SUMMARY_MODEL_PROVIDER,
            model_name=self.SUMMARY_MODEL_NAME,
            prompt_hash=context.prompt_hash,
            provider_receipt_id=None,
            generated_at=now,
            created_at=now,
            updated_at=now,
            error_summary=error_summary,
            stale=False,
        )
        return self.run_ai_summary_repository.create(summary)

    @staticmethod
    def _validate_ai_summary_markdown(markdown: str) -> str | None:
        """Validate AI-generated markdown meets format requirements.

        Returns None if valid, or an error description string if invalid.
        """

        trimmed = markdown.strip()
        if not trimmed:
            return "AI 返回空文本"

        # Must not be wrapped in a code block as the entire body
        if trimmed.startswith("```") and trimmed.endswith("```"):
            return "AI 输出被代码块包裹"

        # Must not be a JSON object
        if trimmed.startswith("{") and trimmed.endswith("}"):
            try:
                json.loads(trimmed)
                return "AI 输出为 JSON 对象而非 Markdown"
            except (json.JSONDecodeError, ValueError):
                pass  # not actually JSON, continue

        # Check for required headings
        for heading in _REQUIRED_HEADINGS:
            if heading not in trimmed:
                return f"缺少必要标题：{heading}"

        # Must have meaningful content beyond just headings
        content_lines = [
            line for line in trimmed.split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]
        if len(content_lines) < 3:
            return "AI 输出内容过短，仅有标题"

        return None

    @staticmethod
    def _compact_text(value: str | None) -> str | None:
        """Collapse one text snippet into a single readable line."""

        if value is None:
            return None

        normalized_value = " ".join(value.split())
        return normalized_value or None
