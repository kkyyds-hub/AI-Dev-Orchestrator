import { useEffect, useRef, useState } from "react";

import {
  getProjectOverviewDefaultTargetId,
  navigateToProjectOverviewHash,
  parseProjectOverviewHash,
  type ProjectOverviewPageView,
} from "../lib/overviewNavigation";

type UseProjectOverviewNavigationStateInput = {
  requestedApprovalId: string | null;
  requestedDeliverableId: string | null;
  selectedProjectId: string | null;
  routeProjectView?: Exclude<ProjectOverviewPageView, "overview"> | null;
  onNavigateToRouteView?: (
    view: ProjectOverviewPageView,
    options?: { projectId?: string | null },
  ) => boolean | void;
};

export function useProjectOverviewNavigationState(
  input: UseProjectOverviewNavigationStateInput,
) {
  const pendingScrollTargetRef = useRef<string | null>(null);
  const scrollRetryTimerRef = useRef<number | null>(null);
  const [scrollRequestNonce, setScrollRequestNonce] = useState(0);
  const [activeView, setActiveView] = useState<ProjectOverviewPageView>("overview");

  const scheduleScrollToTarget = (targetId: string | null | undefined) => {
    pendingScrollTargetRef.current = targetId ?? null;
    setScrollRequestNonce((value) => value + 1);
  };

  const navigateToOverviewSection = (
    sectionId: string,
    options?: { projectId?: string | null },
  ) => {
    setActiveView("overview");
    const routeHandled = input.onNavigateToRouteView?.("overview", {
      projectId: options?.projectId ?? input.selectedProjectId,
    });

    if (!routeHandled) {
      navigateToProjectOverviewHash({
        view: "overview",
        targetId: sectionId,
      });
    }

    scheduleScrollToTarget(sectionId);
  };

  const navigateToOverviewPage = (
    view: Exclude<ProjectOverviewPageView, "overview">,
    targetId?: string | null,
    options?: { projectId?: string | null },
  ) => {
    setActiveView(view);
    const nextTargetId = targetId ?? view;
    const routeHandled = input.onNavigateToRouteView?.(view, {
      projectId: options?.projectId ?? input.selectedProjectId,
    });

    if (!routeHandled) {
      navigateToProjectOverviewHash({
        view,
        targetId: nextTargetId,
      });
    }

    scheduleScrollToTarget(nextTargetId);
  };

  useEffect(() => {
    const clearPendingTimer = () => {
      if (scrollRetryTimerRef.current !== null) {
        window.clearTimeout(scrollRetryTimerRef.current);
        scrollRetryTimerRef.current = null;
      }
    };

    const tryScroll = (retriesLeft: number) => {
      const targetId = pendingScrollTargetRef.current;
      if (!targetId) {
        clearPendingTimer();
        return;
      }

      const element = document.getElementById(targetId);
      if (element) {
        element.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
        pendingScrollTargetRef.current = null;
        clearPendingTimer();
        return;
      }

      if (retriesLeft <= 0) {
        clearPendingTimer();
        return;
      }

      clearPendingTimer();
      scrollRetryTimerRef.current = window.setTimeout(() => {
        tryScroll(retriesLeft - 1);
      }, 120);
    };

    requestAnimationFrame(() => {
      tryScroll(12);
    });

    return clearPendingTimer;
  }, [
    activeView,
    input.requestedApprovalId,
    input.requestedDeliverableId,
    scrollRequestNonce,
    input.selectedProjectId,
  ]);

  useEffect(() => {
    const applyHashNavigation = () => {
      if (window.location.hash.startsWith("#boss-drilldown")) {
        setActiveView("overview");
        scheduleScrollToTarget("project-detail");
        return;
      }

      if (input.routeProjectView) {
        setActiveView(input.routeProjectView);
        scheduleScrollToTarget(getProjectOverviewDefaultTargetId(input.routeProjectView));
        return;
      }

      const parsed = parseProjectOverviewHash(window.location.hash);
      if (!parsed) {
        return;
      }

      setActiveView(parsed.view);
      scheduleScrollToTarget(parsed.targetId ?? parsed.view);
    };

    applyHashNavigation();
    window.addEventListener("hashchange", applyHashNavigation);

    return () => {
      window.removeEventListener("hashchange", applyHashNavigation);
    };
  }, [input.routeProjectView]);

  return {
    activeView,
    navigateToOverviewSection,
    navigateToOverviewPage,
    scheduleScrollToTarget,
  };
}
