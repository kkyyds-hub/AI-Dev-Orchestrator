import { useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import { useBossProjectOverview } from "../../features/projects/hooks";

function getProjectRecencyTimestamp(project: {
  latest_progress_at?: string | null;
  updated_at?: string | null;
  created_at?: string | null;
}) {
  const candidates = [
    project.latest_progress_at,
    project.updated_at,
    project.created_at,
  ];

  for (const candidate of candidates) {
    if (!candidate) {
      continue;
    }
    const parsed = Date.parse(candidate);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }

  return 0;
}

export function useUrlProjectSelection() {
  const [searchParams, setSearchParams] = useSearchParams();
  const overviewQuery = useBossProjectOverview({ enablePolling: false });
  const projects = overviewQuery.data?.projects ?? [];
  const requestedProjectId = searchParams.get("projectId") ?? "";

  const fallbackProjectId = useMemo(() => {
    if (!projects.length) {
      return "";
    }

    return [...projects].sort(
      (left, right) =>
        getProjectRecencyTimestamp(right) - getProjectRecencyTimestamp(left),
    )[0]?.id ?? "";
  }, [projects]);

  const requestedProject = useMemo(
    () =>
      requestedProjectId
        ? projects.find((project) => project.id === requestedProjectId) ?? null
        : null,
    [projects, requestedProjectId],
  );

  const hasInvalidRequestedProject =
    requestedProjectId.length > 0 &&
    projects.length > 0 &&
    requestedProject === null;
  const selectedProjectId = requestedProject?.id ?? fallbackProjectId;
  const selectedProject =
    projects.find((project) => project.id === selectedProjectId) ?? null;

  useEffect(() => {
    if (!projects.length || !selectedProjectId) {
      return;
    }

    if (requestedProjectId === selectedProjectId) {
      return;
    }

    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.set("projectId", selectedProjectId);
    setSearchParams(nextSearchParams, { replace: true });
  }, [
    projects.length,
    requestedProjectId,
    searchParams,
    selectedProjectId,
    setSearchParams,
  ]);

  const setSelectedProjectId = (projectId: string) => {
    const nextSearchParams = new URLSearchParams(searchParams);
    if (projectId) {
      nextSearchParams.set("projectId", projectId);
    } else {
      nextSearchParams.delete("projectId");
    }
    setSearchParams(nextSearchParams, { replace: false });
  };

  return {
    hasInvalidRequestedProject,
    overviewQuery,
    projects,
    requestedProjectId,
    selectedProject,
    selectedProjectId: selectedProjectId || null,
    setSelectedProjectId,
  };
}
