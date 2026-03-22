import type { ConsoleBudget, ConsoleOverview, ConsoleRun, ConsoleTask } from "../console/types";
import type { ConsoleStreamEvent, StreamRunPayload, StreamTaskPayload } from "./types";
import type { TaskDetail } from "../task-detail/types";
import type { RunLogEvent, RunLogResponse } from "../run-log/types";

export function applyConsoleEventToOverview(
  overview: ConsoleOverview,
  streamEvent: ConsoleStreamEvent,
): ConsoleOverview {
  if (streamEvent.type === "task_updated") {
    const updatedTask = toConsoleTask(streamEvent.payload.task);
    const nextTasks = upsertTask(overview.tasks, updatedTask);
    return rebuildOverview(nextTasks, overview.budget);
  }

  if (streamEvent.type === "run_updated") {
    const updatedRun = toConsoleRun(streamEvent.payload.run);
    const currentTask = overview.tasks.find((task) => task.id === streamEvent.payload.task_id);
    const nextTasks = overview.tasks.map((task) => {
      if (task.id !== streamEvent.payload.task_id) {
        return task;
      }

      const latestRun = pickLatestRun(task.latest_run, updatedRun);
      return {
        ...task,
        latest_run: latestRun,
      };
    });

    const nextBudget = currentTask
      ? updateBudgetSnapshot(overview.budget, currentTask.latest_run, updatedRun)
      : overview.budget;
    return rebuildOverview(nextTasks, nextBudget);
  }

  return overview;
}

export function applyConsoleEventToTaskDetail(
  detail: TaskDetail,
  streamEvent: ConsoleStreamEvent,
): TaskDetail {
  if (streamEvent.type === "task_updated" && detail.id === streamEvent.payload.task.id) {
    const task = streamEvent.payload.task;
    return {
      ...detail,
      id: task.id,
      title: task.title,
      status: task.status,
      priority: task.priority,
      input_summary: task.input_summary,
      acceptance_criteria: task.acceptance_criteria,
      depends_on_task_ids: task.depends_on_task_ids,
      risk_level: task.risk_level,
      owner_role_code: task.owner_role_code,
      upstream_role_code: task.upstream_role_code,
      downstream_role_code: task.downstream_role_code,
      human_status: task.human_status,
      paused_reason: task.paused_reason,
      created_at: task.created_at,
      updated_at: task.updated_at,
      context_preview: {
        ...detail.context_preview,
        task_id: task.id,
        task_title: task.title,
        input_summary: task.input_summary,
        acceptance_criteria: task.acceptance_criteria,
        priority: task.priority,
        risk_level: task.risk_level,
        human_status: task.human_status,
        paused_reason: task.paused_reason,
      },
    };
  }

  if (streamEvent.type === "run_updated" && detail.id === streamEvent.payload.task_id) {
    const run = toConsoleRun(streamEvent.payload.run);
    const runs = upsertRun(detail.runs, run);
    return {
      ...detail,
      latest_run: pickLatestRun(detail.latest_run, run),
      runs,
    };
  }

  return detail;
}

export function applyConsoleEventToRunLogs(
  logs: RunLogResponse,
  streamEvent: ConsoleStreamEvent,
): RunLogResponse {
  if (streamEvent.type !== "log_event") {
    return logs;
  }

  if (!streamEvent.payload.run_id || logs.run_id !== streamEvent.payload.run_id) {
    return logs;
  }

  const nextEvent = normalizeRunLogEvent(streamEvent.payload.record);
  const nextEvents = [...logs.events, nextEvent].slice(-logs.limit);
  return {
    ...logs,
    log_path: streamEvent.payload.log_path,
    truncated: logs.truncated || logs.events.length + 1 > logs.limit,
    events: nextEvents,
  };
}

function rebuildOverview(tasks: ConsoleTask[], budget: ConsoleBudget): ConsoleOverview {
  const sortedTasks = [...tasks].sort((left, right) =>
    right.created_at.localeCompare(left.created_at),
  );

  return {
    total_tasks: sortedTasks.length,
    pending_tasks: countByStatus(sortedTasks, "pending"),
    running_tasks: countByStatus(sortedTasks, "running"),
    paused_tasks: countByStatus(sortedTasks, "paused"),
    waiting_human_tasks: countByStatus(sortedTasks, "waiting_human"),
    completed_tasks: countByStatus(sortedTasks, "completed"),
    failed_tasks: countByStatus(sortedTasks, "failed"),
    blocked_tasks: countByStatus(sortedTasks, "blocked"),
    total_estimated_cost: roundMetric(
      sortedTasks.reduce(
        (sum, task) => sum + (task.latest_run?.estimated_cost ?? 0),
        0,
      ),
    ),
    total_prompt_tokens: sortedTasks.reduce(
      (sum, task) => sum + (task.latest_run?.prompt_tokens ?? 0),
      0,
    ),
    total_completion_tokens: sortedTasks.reduce(
      (sum, task) => sum + (task.latest_run?.completion_tokens ?? 0),
      0,
    ),
    budget,
    tasks: sortedTasks,
  };
}

function countByStatus(tasks: ConsoleTask[], status: string): number {
  return tasks.filter((task) => task.status === status).length;
}

function upsertTask(tasks: ConsoleTask[], updatedTask: ConsoleTask): ConsoleTask[] {
  const existingTask = tasks.find((task) => task.id === updatedTask.id);
  if (!existingTask) {
    return [updatedTask, ...tasks];
  }

  return tasks.map((task) =>
    task.id === updatedTask.id
      ? {
          ...updatedTask,
          latest_run: task.latest_run,
        }
      : task,
  );
}

function upsertRun(runs: ConsoleRun[], updatedRun: ConsoleRun): ConsoleRun[] {
  const exists = runs.some((run) => run.id === updatedRun.id);
  const nextRuns = exists
    ? runs.map((run) => (run.id === updatedRun.id ? updatedRun : run))
    : [updatedRun, ...runs];

  return nextRuns.sort((left, right) => right.created_at.localeCompare(left.created_at));
}

function pickLatestRun(
  currentRun: ConsoleRun | null,
  candidateRun: ConsoleRun,
): ConsoleRun {
  if (!currentRun) {
    return candidateRun;
  }

  if (currentRun.id === candidateRun.id) {
    return candidateRun;
  }

  return candidateRun.created_at >= currentRun.created_at ? candidateRun : currentRun;
}

function toConsoleTask(task: StreamTaskPayload): ConsoleTask {
  return {
    ...task,
    latest_run: null,
  };
}

function toConsoleRun(run: StreamRunPayload): ConsoleRun {
  return {
    id: run.id,
    status: run.status,
    route_reason: run.route_reason,
    routing_score: run.routing_score,
    routing_score_breakdown: run.routing_score_breakdown,
    owner_role_code: run.owner_role_code,
    upstream_role_code: run.upstream_role_code,
    downstream_role_code: run.downstream_role_code,
    handoff_reason: run.handoff_reason,
    dispatch_status: run.dispatch_status,
    result_summary: run.result_summary,
    prompt_tokens: run.prompt_tokens,
    completion_tokens: run.completion_tokens,
    estimated_cost: run.estimated_cost,
    log_path: run.log_path,
    verification_mode: run.verification_mode,
    verification_template: run.verification_template,
    verification_command: run.verification_command,
    verification_summary: run.verification_summary,
    failure_category: run.failure_category,
    quality_gate_passed: run.quality_gate_passed,
    started_at: run.started_at,
    finished_at: run.finished_at,
    created_at: run.created_at,
  };
}

function updateBudgetSnapshot(
  budget: ConsoleBudget,
  previousLatestRun: ConsoleRun | null,
  updatedRun: ConsoleRun,
): ConsoleBudget {
  const previousCost =
    previousLatestRun?.id === updatedRun.id ? previousLatestRun.estimated_cost : 0;
  const costDelta = roundMetric(updatedRun.estimated_cost - previousCost);

  if (costDelta === 0) {
    return budget;
  }

  const sessionCostUsed = roundMetric(Math.max(budget.session_cost_used + costDelta, 0));
  const dailyCostUsed = isRunInDailyWindow(updatedRun, budget)
    ? roundMetric(Math.max(budget.daily_cost_used + costDelta, 0))
    : budget.daily_cost_used;

  return {
    ...budget,
    daily_cost_used: dailyCostUsed,
    daily_cost_remaining: roundMetric(Math.max(budget.daily_budget_usd - dailyCostUsed, 0)),
    daily_budget_exceeded: dailyCostUsed >= budget.daily_budget_usd,
    session_cost_used: sessionCostUsed,
    session_cost_remaining: roundMetric(
      Math.max(budget.session_budget_usd - sessionCostUsed, 0),
    ),
    session_budget_exceeded: sessionCostUsed >= budget.session_budget_usd,
  };
}

function isRunInDailyWindow(run: ConsoleRun, budget: ConsoleBudget): boolean {
  return Date.parse(run.created_at) >= Date.parse(budget.daily_window_started_at);
}

function normalizeRunLogEvent(record: RunLogEvent): RunLogEvent {
  return {
    timestamp: record.timestamp,
    level: record.level,
    event: record.event,
    message: record.message,
    data: record.data ?? {},
  };
}

function roundMetric(value: number): number {
  return Math.round(value * 1_000_000) / 1_000_000;
}
