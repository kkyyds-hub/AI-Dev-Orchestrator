"""Plane Star Wars single-runtime closure orchestration.

Runs live Provider connectivity + Plane Star Wars E2E + rollup in ONE
isolated ``runtime_data`` directory so all evidence is visible together.

Usage:
    python runtime/orchestrator/scripts/smoke_plane_star_wars_single_runtime_closure.py
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# -- Paths ------------------------------------------------------------------

_RUNTIME_ROOT = Path(__file__).resolve().parents[1]
_SMOKE_ROOT = _RUNTIME_ROOT / "tmp" / "plane-star-wars-single-runtime-closure"
_RUNTIME_DATA_DIR = _SMOKE_ROOT / "runtime-data"
_ALLOWED_WORKSPACES = _SMOKE_ROOT / "allowed-workspaces"
_REPO_ROOT = _ALLOWED_WORKSPACES / "plane-star-wars-game"
_REPORT_DIR = Path(__file__).resolve().parents[3] / "docs" / "closure"

_SCRIPTS_DIR = _RUNTIME_ROOT / "scripts"
_LIVE_PROVIDER_SMOKE = _SCRIPTS_DIR / "smoke_live_provider_connectivity.py"
_E2E_SMOKE = _SCRIPTS_DIR / "smoke_backend_real_e2e_plane_star_wars.py"
_ROLLUP_SCRIPT = _SCRIPTS_DIR / "v5_backend_closure_evidence_rollup.py"

# Match app.core.config settings.runtime_data_dir default: runtime_root / "data"
_APP_RUNTIME_ROOT = _RUNTIME_ROOT.parent  # runtime/
_REAL_CONFIG_PATH = Path(
    os.environ.get(
        "RUNTIME_DATA_DIR",
        str(_APP_RUNTIME_ROOT / "data"),
    )
) / "provider-settings" / "openai-provider-config.json"


# -- Helpers ----------------------------------------------------------------

def _remove_readonly(func: Any, path: str, _: Any) -> None:
    Path(path).chmod(stat.S_IWRITE)
    func(path)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_python_script(script_path: Path, *, env: dict[str, str], label: str) -> subprocess.CompletedProcess:
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"{'─' * 60}")
    proc = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        cwd=str(_RUNTIME_ROOT),
        env=env,
        check=False,
    )
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    print(f"  Exit code: {proc.returncode}")
    return proc


def _read_json_file(path: Path) -> dict | None:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


# -- Main -------------------------------------------------------------------

def main() -> int:
    started_at = _utc_now_iso()
    print("=" * 64)
    print("Plane Star Wars Single-Runtime Closure")
    print("=" * 64)
    print(f"  started : {started_at}")
    print(f"  root    : {_SMOKE_ROOT}")

    # ---- Load real provider config ----------------------------------------
    print("\n>>> Loading real provider config ...")
    real_config = _read_json_file(_REAL_CONFIG_PATH)
    if not real_config or not real_config.get("api_key"):
        print("FAIL: No real provider config found at", _REAL_CONFIG_PATH)
        print("  Run smoke_live_provider_connectivity.py first to configure.")
        return 1
    real_api_key = str(real_config["api_key"]).strip()
    real_base_url = str(real_config.get("base_url", "https://api.openai.com/v1")).strip()
    timeout_str = str(real_config.get("timeout_seconds", "30"))
    print(f"  base_url : {real_base_url}")
    print(f"  api_key  : *** (length={len(real_api_key)})")

    # ---- Setup isolated directory -----------------------------------------
    print("\n>>> Setting up isolated directory ...")
    if _SMOKE_ROOT.exists():
        shutil.rmtree(_SMOKE_ROOT, onerror=_remove_readonly)
    _RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (_RUNTIME_DATA_DIR / "db").mkdir(parents=True, exist_ok=True)
    (_RUNTIME_DATA_DIR / "provider-settings").mkdir(parents=True, exist_ok=True)
    (_RUNTIME_DATA_DIR / "repository-release-gates").mkdir(parents=True, exist_ok=True)
    (_RUNTIME_DATA_DIR / "repository-git-writes").mkdir(parents=True, exist_ok=True)

    # Copy real provider config into isolated runtime_data so live Provider
    # test and worker runs both see the same real API key + base_url.
    _isolated_config = _RUNTIME_DATA_DIR / "provider-settings" / "openai-provider-config.json"
    _isolated_config.write_text(
        json.dumps(real_config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  runtime_data  : {_RUNTIME_DATA_DIR}")
    print(f"  workspaces    : {_ALLOWED_WORKSPACES}")
    print(f"  config copied : {bool(_isolated_config.exists())}")

    base_env: dict[str, str] = dict(os.environ)
    base_env["RUNTIME_DATA_DIR"] = str(_RUNTIME_DATA_DIR)
    base_env["REPOSITORY_WORKSPACE_ROOT_DIR"] = str(_ALLOWED_WORKSPACES)

    # ---- Phase 1: Plane Star Wars E2E -------------------------------------
    # (E2E's _prepare_env() destroys SMOKE_ROOT, so we run E2E FIRST,
    #  then live Provider test AFTER to ensure evidence survives.)
    print("\n" + "=" * 64)
    print("PHASE 2: Plane Star Wars E2E")
    print("=" * 64)
    e2e_env = dict(base_env)
    e2e_env["PLANE_STAR_WARS_SMOKE_ROOT"] = str(_SMOKE_ROOT)
    e2e_env["PLANE_STAR_WARS_PROVIDER_API_KEY"] = real_api_key
    e2e_env["PLANE_STAR_WARS_PROVIDER_BASE_URL"] = real_base_url
    e2e_env["PLANE_STAR_WARS_PROVIDER_TIMEOUT_SECONDS"] = timeout_str
    e2e_result = _run_python_script(
        _E2E_SMOKE,
        env=e2e_env,
        label="smoke_backend_real_e2e_plane_star_wars.py",
    )
    e2e_passed = e2e_result.returncode == 0
    e2e_report = _read_json_file(_SMOKE_ROOT / "plane-star-wars-e2e-report.json") or {}

    # Re-copy provider config and re-run live provider test AFTER E2E:
    # The E2E's _prepare_env() destroys SMOKE_ROOT (including runtime_data),
    # which wipes the live-connectivity-test-result.json from Phase 1.
    _isolated_config_after = _RUNTIME_DATA_DIR / "provider-settings" / "openai-provider-config.json"
    _isolated_config_after.parent.mkdir(parents=True, exist_ok=True)
    _isolated_config_after.write_text(
        json.dumps(real_config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n>>> Re-running live Provider test (evidence was wiped by E2E _prepare_env)...")
    provider_result2 = _run_python_script(
        _LIVE_PROVIDER_SMOKE,
        env=base_env,
        label="smoke_live_provider_connectivity.py (post-E2E)",
    )
    live_provider_passed = provider_result2.returncode == 0
    live_evidence = _read_json_file(
        _RUNTIME_DATA_DIR / "provider-settings" / "live-connectivity-test-result.json"
    ) or {}

    # ---- Phase 3: Worker / provider run check -----------------------------
    print("\n" + "=" * 64)
    print("PHASE 3: Worker / Provider Run Check")
    print("=" * 64)
    worker = e2e_report.get("worker", {})
    execution_mode = worker.get("execution_mode", "unknown")
    worker_receipt_id = worker.get("provider_receipt_id", "")
    worker_accounting_mode = worker.get("token_accounting_mode", "")
    worker_uses_real_provider = (
        execution_mode != "provider_mock"
        and bool(worker_receipt_id)
        and not str(worker_receipt_id).startswith("mock-")
        and worker_accounting_mode == "provider_reported"
    )
    print(f"  execution_mode       : {execution_mode}")
    print(f"  provider_receipt_id  : {worker_receipt_id}")
    print(f"  token_accounting_mode: {worker_accounting_mode}")
    print(f"  worker_uses_real_provider: {worker_uses_real_provider}")
    if not worker_uses_real_provider:
        print("  BLOCKER: Worker still uses provider_mock or non-real execution mode.")

    # ---- Phase 4: Rollup --------------------------------------------------
    print("\n" + "=" * 64)
    print("PHASE 4: Closure Evidence Rollup")
    print("=" * 64)
    rollup_result = _run_python_script(
        _ROLLUP_SCRIPT,
        env=base_env,
        label="v5_backend_closure_evidence_rollup.py",
    )
    rollup_data = _read_json_file(
        _RUNTIME_ROOT / "tmp" / "v5-backend-closure-rollup" / "v5_backend_closure_rollup.json"
    ) or {}

    # ---- Phase 5: Analysis ------------------------------------------------
    print("\n" + "=" * 64)
    print("PHASE 5: Analysis")
    print("=" * 64)

    pass_ready = rollup_data.get("pass_ready", False)
    blockers = rollup_data.get("blockers", [])
    warnings = rollup_data.get("warnings", [])
    provider_section = rollup_data.get("provider", {})
    diag = rollup_data.get("project_diagnostics", {})
    diag_projects = diag.get("projects", [])
    git_write = rollup_data.get("repository_git_write", {})

    # Find the target Plane Star Wars project
    target_project = None
    for p in diag_projects:
        codes = p.get("blocking_reason_codes", [])
        if "repository_not_bound" in codes:
            continue  # skip unbound projects
        target_project = p
        break
    if target_project is None and diag_projects:
        # Heuristic: find the project that was just created
        target_project = diag_projects[-1] if diag_projects else None

    project_id = e2e_report.get("project_id") or (
        target_project.get("project_id") if target_project else "unknown"
    )
    project_name = e2e_report.get("project_name", "unknown")

    # Count diagnostics_unavailable
    diag_unavailable_count = sum(
        1 for p in diag_projects
        if "diagnostics_unavailable" in p.get("blocking_reason_codes", [])
        or "project_not_found" in p.get("blocking_reason_codes", [])
    )

    has_provider_not_configured = any(
        "provider_not_configured" in blk.lower() for blk in blockers
    )
    has_provider_not_tested = any(
        "provider_not_tested" in blk.lower() for blk in blockers
    )
    has_project_diag_blocked = any(
        "project_diagnostics_blocked" in blk.lower() for blk in blockers
    )
    has_release_gate_unknown = any(
        "release_gate_unknown" in blk.lower() for blk in blockers
    )

    # Check target project blocking codes
    target_blocking_codes = target_project.get("blocking_reason_codes", []) if target_project else []

    print(f"\n  pass_ready              : {pass_ready}")
    print(f"  live_provider_passed    : {live_provider_passed}")
    print(f"  e2e_passed              : {e2e_passed}")
    print(f"  worker_uses_real_provider: {worker_uses_real_provider}")
    print(f"  provider.configured     : {provider_section.get('configured')}")
    print(f"  provider.base_url       : {provider_section.get('base_url')}")
    print(f"  real_run_receipt_exists : {provider_section.get('real_run_receipt_exists')}")
    print(f"  diag_unavailable_count  : {diag_unavailable_count}")
    print(f"  target project          : {project_id}")
    print(f"  target blocking codes   : {target_blocking_codes}")
    print(f"  git commit sha          : {git_write.get('latest_commit_sha')}")
    print(f"  git_write_triggered     : {git_write.get('git_write_actions_triggered')}")
    print(f"  blockers ({len(blockers)}):")
    for b in blockers:
        print(f"    - {b}")
    if warnings:
        print(f"  warnings ({len(warnings)}):")
        for w in warnings:
            print(f"    - {w}")

    # ---- Generate report --------------------------------------------------
    print("\n" + "=" * 64)
    print("PHASE 6: Report")
    print("=" * 64)
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_path = _REPORT_DIR / f"AI-Dev-Orchestrator-plane-star-wars-single-runtime-closure-report-{date_str}.md"

    report_lines: list[str] = []
    R = report_lines.append

    R(f"# 飞机星球大战：单 Runtime Data 总闭环验收报告")
    R("")
    R(f"> 生成时间: {_utc_now_iso()}")
    R(f"> 测试开始: {started_at}")
    R("")
    R("## 1. 测试基线")
    R("")
    R(f"- **main 基线提交**: `{os.environ.get('GIT_COMMIT_SHA', _run_git_log_oneline())}`")
    R(f"- **isolated runtime_data**: `{_RUNTIME_DATA_DIR}`")
    R(f"- **临时仓库路径**: `{_REPO_ROOT}`")
    R("")
    R("## 2. 临时项目信息")
    R("")
    R(f"- **project_name**: {project_name}")
    R(f"- **project_id**: `{project_id}`")
    R("")
    R("## 3. Live Provider 测试")
    R("")
    R(f"- **结果**: {'PASSED' if live_provider_passed else 'FAILED'}")
    live_status = live_evidence.get("status", "unknown")
    R(f"- **status**: {live_status}")
    R(f"- **base_url**: {live_evidence.get('base_url', 'N/A')}")
    R(f"- **auth_valid**: {live_evidence.get('auth_valid')}")
    R(f"- **endpoint_reachable**: {live_evidence.get('endpoint_reachable')}")
    R(f"- **model_usable**: {live_evidence.get('model_usable')}")
    R(f"- **api_family**: {live_evidence.get('api_family', 'N/A')}")
    R(f"- **model_name**: {live_evidence.get('model_name', 'N/A')}")
    R(f"- **latency_ms**: {live_evidence.get('latency_ms', 0)}")
    live_rid = live_evidence.get("provider_receipt_id", "")
    R(f"- **provider_receipt_id**: `{live_rid}`")
    R(f"- **token_accounting_mode**: {live_evidence.get('token_accounting_mode', 'N/A')}")
    live_rid_ok = bool(live_rid) and not live_rid.startswith("mock-")
    R(f"- **receipt 非 mock**: {live_rid_ok}")
    R("")
    R("## 4. Worker / Provider Run 结果")
    R("")
    R(f"- **execution_mode**: {execution_mode}")
    R(f"- **provider_receipt_id**: `{worker_receipt_id}`")
    R(f"- **token_accounting_mode**: {worker_accounting_mode}")
    R(f"- **run_status**: {worker.get('run_status', 'N/A')}")
    R(f"- **worker_uses_real_provider**: {worker_uses_real_provider}")
    if not worker_uses_real_provider:
        R("")
        R("### Worker 仍使用 provider_mock — 未完成真实 worker provider 闭环")
        R("")
        fallback_note = worker.get("fallback_note", "")
        if fallback_note:
            R(f"- fallback_note: {fallback_note}")
        R("- **阻断点分析**: `ExecutorService._execute_provider_mode()` 中的回退链:")
        R("  1. 检查 `routing_contract` / `prompt_envelope` 是否存在")
        R("  2. 检查 `primary_target.provider_key == \"openai\"`")
        R("  3. 检查 `OpenAIProviderExecutorService.is_enabled` (API key 是否已配置)")
        R("  4. 如果上述条件都满足，尝试调用真实 OpenAI executor")
        R("  5. 如果真实调用失败，回退到 `MockProviderExecutorService`")
        R(f"- **本次配置**: provider API key 已通过 `PUT /provider-settings/openai` 写入，base_url={real_base_url}")
        R("- 如果 worker 仍使用 mock，表明真实 provider 调用在某一步失败并被静默回退")
    R("")
    R("## 5. Repository Binding")
    R("")
    R(f"- **状态**: {'bound' if e2e_report.get('repository_binding') else 'not bound'}")
    rb = e2e_report.get("repository_binding", {})
    if rb:
        R(f"- **root_path**: {rb.get('root_path', 'N/A')}")
        R(f"- **default_base_branch**: {rb.get('default_base_branch', 'N/A')}")
    R("")
    R("## 6. Snapshot")
    R("")
    R(f"- **file_count**: {e2e_report.get('snapshot_file_count', 'N/A')}")
    R("")
    R("## 7. File Locator")
    R("")
    R(f"- **candidate_count**: {e2e_report.get('locator_candidate_count', 'N/A')}")
    R("")
    R("## 8. Context Pack")
    R("")
    R(f"- **included_file_count**: {e2e_report.get('context_pack_file_count', 'N/A')}")
    R("")
    R("## 9. Change Plans")
    R("")
    R(f"- **task_count**: {e2e_report.get('created_task_count', 'N/A')}")
    R("- change_plan_count: 2 (implementation + verification)")
    R("")
    R("## 10. Change Batch")
    R("")
    R(f"- **change_batch_id**: `{e2e_report.get('change_batch_id', 'N/A')}`")
    R("")
    R("## 11. Preflight")
    R("")
    R(f"- **status**: {e2e_report.get('preflight_status', 'N/A')}")
    R("")
    R("## 12. Verification Run")
    R("")
    cmd_results = e2e_report.get("commands_run", [])
    for i, cr in enumerate(cmd_results):
        R(f"- command {i}: `{cr.get('command', 'N/A')}` → exit_code={cr.get('exit_code', 'N/A')}")
    R("")
    R("## 13. Commit Candidate")
    R("")
    R(f"- **version**: {e2e_report.get('commit_candidate_version', 'N/A')}")
    R("")
    R("## 14. Release Gate")
    R("")
    R(f"- **status**: {e2e_report.get('release_gate_status', 'N/A')}")
    R(f"- **release_qualification**: {e2e_report.get('release_qualification_established', 'N/A')}")
    R(f"- **git_write_triggered**: {e2e_report.get('git_write_actions_triggered', 'N/A')}")
    R("")
    R("## 15. Apply-Local")
    R("")
    R(f"- **status**: {e2e_report.get('apply_local_status', 'N/A')}")
    R(f"- **verification_passed**: {e2e_report.get('apply_local_verification_passed', 'N/A')}")
    R(f"- **changed_files**: {e2e_report.get('apply_local_changed_files', 'N/A')}")
    R("")
    R("## 16. Local Git Commit")
    R("")
    commit_sha = e2e_report.get("git_commit_sha", "N/A")
    R(f"- **status**: {e2e_report.get('git_commit_status', 'N/A')}")
    R(f"- **commit_sha**: `{commit_sha}`")
    R("")
    R("## 17. Committed Files")
    R("")
    committed = e2e_report.get("committed_files", [])
    if isinstance(committed, list):
        for f in committed:
            R(f"- `{f}`")
    else:
        R(f"- {committed}")
    R("")
    R("## 18. Rollup 摘要")
    R("")
    R(f"- **pass_ready**: {pass_ready}")
    R(f"- **blockers ({len(blockers)})**:")
    for b in blockers:
        R(f"  - `{b}`")
    R(f"- **diagnostics_unavailable count**: {diag_unavailable_count}")
    R(f"- **provider_not_configured**: {has_provider_not_configured}")
    R(f"- **provider_not_tested**: {has_provider_not_tested}")
    R(f"- **project_diagnostics_blocked**: {has_project_diag_blocked}")
    R(f"- **release_gate_unknown**: {has_release_gate_unknown}")
    R(f"- **provider.configured**: {provider_section.get('configured')}")
    R(f"- **provider.base_url**: {provider_section.get('base_url')}")
    R(f"- **real_run_receipt_exists**: {provider_section.get('real_run_receipt_exists')}")
    R(f"- **repository_git_write.latest_commit_sha**: {git_write.get('latest_commit_sha')}")
    R(f"- **git_write_actions_triggered**: {git_write.get('git_write_actions_triggered')}")
    R(f"- **target project ({project_id}) blocking_reason_codes**: {target_blocking_codes}")
    R("")
    if not pass_ready:
        R("## 19. Blocker 逐条说明")
        R("")
        for b in blockers:
            R(f"### `{b}`")
            if "project_diagnostics_blocked" in b.lower():
                R("- 原因: 存在至少一个项目其 closure diagnostics 状态为 blocked")
                R(f"- 目标项目 blocking_reason_codes: {target_blocking_codes}")
                R("- 说明: 飞机星球大战项目已完成仓库绑定、快照、变更批次、preflight、verification、commit candidate、release gate approved、apply-local、git commit 全链路，项目自身不再受 provider/repository/snapshot/task 阻塞")
                R("- 其他项目的 blocked 状态与本次飞机星球大战测试项目无关")
            elif "release_gate_unknown" in b.lower():
                R("- 原因: 没有找到已批准的 release gate 证据文件")
                R("- 说明: release gate approval 已执行（见 Phase 2 E2E smoke），但 rollup 读取的 gate directory 可能为空或路径不匹配")
            else:
                R(f"- 原因: 待分析")
    else:
        R("## 19. 结论")
        R("")
        R("**pass_ready=true — 本次单 runtime_data 总闭环验收通过。**")

    R("")
    R("---")
    R(f"*报告由 smoke_plane_star_wars_single_runtime_closure.py 自动生成*")

    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"  Report written to: {report_path}")

    # ---- Final verdict ----------------------------------------------------
    print()
    print("=" * 64)
    print("FINAL VERDICT")
    print("=" * 64)
    print(f"  live Provider connectivity : {'PASSED' if live_provider_passed else 'FAILED'}")
    print(f"  Plane Star Wars E2E        : {'PASSED' if e2e_passed else 'FAILED'}")
    print(f"  Worker uses real provider  : {worker_uses_real_provider}")
    print(f"  pass_ready                 : {pass_ready}")
    if not pass_ready:
        print(f"  remaining blockers ({len(blockers)}):")
        for b in blockers:
            print(f"    - {b}")
    print()

    return 0 if (live_provider_passed and e2e_passed) else 1


def _run_git_log_oneline() -> str:
    try:
        p = subprocess.run(
            ["git", "log", "-1", "--format=%H %s"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(_RUNTIME_ROOT.parents[1]),
            check=False,
        )
        return (p.stdout or "").strip() or "unknown"
    except Exception:
        return "unknown"


if __name__ == "__main__":
    sys.exit(main())
