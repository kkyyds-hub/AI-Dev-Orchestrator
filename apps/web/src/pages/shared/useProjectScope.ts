import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useBossProjectOverview } from "../../features/projects/hooks";

const SHARED_KEY = "ai-dev-orchestrator:selected-project-id";
const LEGACY_KEY = "ai-dev-orchestrator:tasks-selected-project-id";

function readStoredProjectId(): string | null {
  try {
    return (
      localStorage.getItem(SHARED_KEY) ??
      localStorage.getItem(LEGACY_KEY) ??
      null
    );
  } catch {
    return null;
  }
}

function writeStoredProjectId(projectId: string | null) {
  try {
    if (projectId) {
      localStorage.setItem(SHARED_KEY, projectId);
    } else {
      localStorage.removeItem(SHARED_KEY);
    }
    // Clean up legacy key on write so all pages converge
    localStorage.removeItem(LEGACY_KEY);
  } catch {
    // storage unavailable — ignore
  }
}

function resolveInitialProjectId(searchParams: URLSearchParams): string {
  const urlId = searchParams.get("projectId");
  if (urlId) return urlId;
  const stored = readStoredProjectId();
  if (stored) return stored;
  return "all";
}

export function useProjectScope() {
  const [searchParams, setSearchParams] = useSearchParams();
  const projectOverviewQuery = useBossProjectOverview({ enablePolling: false });
  const projects = projectOverviewQuery.data?.projects ?? [];

  const [selectedProjectId, _setSelectedProjectId] = useState<string>(
    () => resolveInitialProjectId(searchParams),
  );

  // Sync URL → state (browser back/forward)
  // Only override from URL when URL explicitly has a projectId.
  // When URL has no projectId, keep current state (from localStorage init
  // or a prior selection) — do NOT force "all".
  useEffect(() => {
    const urlId = searchParams.get("projectId");
    if (urlId) {
      _setSelectedProjectId((current) =>
        current !== urlId ? urlId : current,
      );
    }
  }, [searchParams]);

  const setSelectedProjectId = useCallback(
    (nextId: string) => {
      _setSelectedProjectId(nextId);
      writeStoredProjectId(nextId === "all" ? null : nextId);
      const nextParams = new URLSearchParams(searchParams);
      if (nextId === "all") {
        nextParams.delete("projectId");
      } else {
        nextParams.set("projectId", nextId);
      }
      setSearchParams(nextParams, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  /** Whether project list is loaded AND selectedProjectId is a
   *  specific (non-"all") ID that doesn't exist in the project list. */
  const projectNotFound = useMemo(
    () =>
      selectedProjectId !== "all" &&
      !projectOverviewQuery.isLoading &&
      projects.length > 0 &&
      !projects.some((p) => p.id === selectedProjectId),
    [projects, projectOverviewQuery.isLoading, selectedProjectId],
  );

  const selectedProjectName = useMemo(() => {
    if (selectedProjectId === "all") return "全部项目";
    return (
      projects.find((p) => p.id === selectedProjectId)?.name ?? "未知项目"
    );
  }, [projects, selectedProjectId]);

  return {
    /** "all" or a project UUID */
    selectedProjectId,
    /** Update the project scope (persists to URL + localStorage) */
    setSelectedProjectId,
    /** Human-readable name for the currently selected scope */
    selectedProjectName,
    /** Available projects from boss overview */
    projects,
    /** Whether the projects query is still loading */
    projectsLoading: projectOverviewQuery.isLoading,
    /** True when a specific project ID was requested but isn't in the list */
    projectNotFound,
  };
}
