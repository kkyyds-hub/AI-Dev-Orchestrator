import { useEffect, useRef, useState } from "react";

import {
  navigateToProjectOverviewHash,
  parseProjectOverviewHash,
  type ProjectOverviewPageView,
} from "../lib/overviewNavigation";

type UseProjectOverviewNavigationStateInput = {
  requestedApprovalId: string | null;
  requestedDeliverableId: string | null;
  selectedProjectId: string | null;
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

  const navigateToOverviewSection = (sectionId: string) => {
    setActiveView("overview");
    navigateToProjectOverviewHash({
      view: "overview",
      targetId: sectionId,
    });
    scheduleScrollToTarget(sectionId);
  };

  const navigateToOverviewPage = (
    view: Exclude<ProjectOverviewPageView, "overview">,
    targetId?: string | null,
  ) => {
    setActiveView(view);
    navigateToProjectOverviewHash({
      view,
      targetId: targetId ?? view,
    });
    scheduleScrollToTarget(targetId ?? view);
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
  }, []);

  return {
    activeView,
    navigateToOverviewSection,
    navigateToOverviewPage,
    scheduleScrollToTarget,
  };
}
