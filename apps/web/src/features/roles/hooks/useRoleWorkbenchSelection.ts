import { useEffect, useMemo, useState } from "react";

import type {
  RoleWorkbenchHandoffItem,
  RoleWorkbenchLane,
  RoleWorkbenchTaskItem,
} from "../types";

export function useRoleWorkbenchSelection(
  lanes: RoleWorkbenchLane[],
  handoffs: RoleWorkbenchHandoffItem[],
) {
  const [selectedRoleCode, setSelectedRoleCode] = useState<string | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [selectedHandoffId, setSelectedHandoffId] = useState<string | null>(null);

  useEffect(() => {
    if (!lanes.length) {
      setSelectedRoleCode(null);
      return;
    }

    const roleStillExists = lanes.some((lane) => lane.role_code === selectedRoleCode);
    if (!selectedRoleCode || !roleStillExists) {
      setSelectedRoleCode(lanes.find((lane) => lane.enabled)?.role_code ?? lanes[0].role_code);
    }
  }, [lanes, selectedRoleCode]);

  const flattenedTasks = useMemo(() => {
    const taskMap = new Map<string, RoleWorkbenchTaskItem>();
    for (const lane of lanes) {
      for (const task of [
        ...lane.current_tasks,
        ...lane.blocked_tasks,
        ...lane.running_tasks,
      ]) {
        taskMap.set(task.task_id, task);
      }
    }
    return Array.from(taskMap.values());
  }, [lanes]);

  useEffect(() => {
    if (!flattenedTasks.length) {
      setSelectedTaskId(null);
      return;
    }

    const taskStillExists = flattenedTasks.some((task) => task.task_id === selectedTaskId);
    if (!selectedTaskId || !taskStillExists) {
      const preferredLane = lanes.find((lane) => lane.role_code === selectedRoleCode);
      const fallbackTask = preferredLane?.current_tasks[0] ?? flattenedTasks[0];
      setSelectedTaskId(fallbackTask?.task_id ?? null);
    }
  }, [flattenedTasks, lanes, selectedRoleCode, selectedTaskId]);

  useEffect(() => {
    if (!handoffs.length) {
      setSelectedHandoffId(null);
      return;
    }

    const handoffStillExists = handoffs.some((handoff) => handoff.id === selectedHandoffId);
    if (!selectedHandoffId || !handoffStillExists) {
      setSelectedHandoffId(handoffs[0].id);
    }
  }, [handoffs, selectedHandoffId]);

  const selectedRole = useMemo<RoleWorkbenchLane | null>(
    () => lanes.find((lane) => lane.role_code === selectedRoleCode) ?? null,
    [lanes, selectedRoleCode],
  );
  const selectedTask = useMemo<RoleWorkbenchTaskItem | null>(
    () => flattenedTasks.find((task) => task.task_id === selectedTaskId) ?? null,
    [flattenedTasks, selectedTaskId],
  );
  const selectedHandoff = useMemo<RoleWorkbenchHandoffItem | null>(
    () => handoffs.find((handoff) => handoff.id === selectedHandoffId) ?? null,
    [handoffs, selectedHandoffId],
  );

  function selectTask(task: RoleWorkbenchTaskItem) {
    setSelectedTaskId(task.task_id);
    if (task.owner_role_code) {
      setSelectedRoleCode(task.owner_role_code);
    }
  }

  function selectHandoff(handoff: RoleWorkbenchHandoffItem) {
    setSelectedHandoffId(handoff.id);
    setSelectedTaskId(handoff.task_id);
    if (handoff.owner_role_code) {
      setSelectedRoleCode(handoff.owner_role_code);
    }
  }

  return {
    selectedRoleCode,
    selectedTaskId,
    selectedHandoffId,
    selectedRole,
    selectedTask,
    selectedHandoff,
    setSelectedRoleCode,
    selectTask,
    selectHandoff,
  };
}
