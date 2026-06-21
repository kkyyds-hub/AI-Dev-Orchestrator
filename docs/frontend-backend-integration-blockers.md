# Frontend / Backend Integration Blockers

Last updated: 2026-06-21

This document records backend gaps or backend semantics that the formal workbench must degrade around. These items must not be hidden as success states in the UI.

## Repository Unbound State Returns 404

- Surface / route: `/projects/:projectId/repository`
- Frontend expectation: A project without a bound repository is a normal pending-binding state. The repository page should keep the shared lab workbench shell, show an empty / pending-binding state, and keep the repository binding panel available.
- Current backend endpoint and actual return:
  - `GET /repositories/projects/{project_id}` returns `404` with `Repository workspace not found for project`.
  - `GET /repositories/projects/{project_id}/snapshot` returns `404` with `Repository snapshot not found for project`.
  - `GET /repositories/projects/{project_id}/verification-baseline` returns `404` when no repository workspace exists.
  - `GET /repositories/projects/{project_id}/change-session` returns `404` when no repository workspace or active change session exists.
- Why this is a blocker / gap: These 404 responses can represent a normal business state rather than an unrecoverable backend failure. If the frontend treats them as generic query errors, ordinary users see a repository failure page and lose the binding path.
- Temporary frontend degradation strategy: Repository adapter maps `snapshot`, `verification-baseline`, and `change-session` 404 responses to `null`; the repository view model maps a selected project without workspace to `pending_binding`; the shared repository page renders the empty state plus `WorkbenchRepositoryBindingPanel`.
- Backend follow-up: Return a typed empty-state response or a structured error code that distinguishes `project_not_found`, `repository_not_bound`, `snapshot_not_generated`, `verification_baseline_not_ready`, and `change_session_not_created`.

## Claude Code / Worker Deep Execution Is Deferred

- Surface / route: `/execution`, `/tasks`, `/tasks/:taskId`, `/runs`
- Frontend expectation: Ordinary users should see readable task / execution progress and safe next actions without run IDs, worker internals, provider receipts, log paths, token details, or write controls.
- Current backend endpoint and actual return:
  - `GET /tasks`, `GET /tasks/{task_id}`, `GET /tasks/{task_id}/runs`, and `GET /runs/{run_id}/logs` expose the current runtime read model, but deep Claude Code executor launch and worker execution control are not in this round's hard scope.
- Why this is a blocker / gap: The formal frontend can show real task and run summaries, but it cannot honestly claim full deep execution control until backend execution semantics are completed.
- Temporary frontend degradation strategy: The execution surface uses the real task/run APIs for read-only summaries, sanitizes run log messages, and keeps write / launch / commit / push actions out of the ordinary UI.
- Backend follow-up: Add product-level execution endpoints that expose user-facing execution states and allowed actions without leaking worker implementation fields.
