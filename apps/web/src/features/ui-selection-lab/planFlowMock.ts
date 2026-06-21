export type PlanFlowStage = "draft" | "changes_requested" | "rejected" | "confirmed" | "created";

export interface PlanFlowState {
  stage: PlanFlowStage;
  title: string;
  summary: string;
  projectName: string;
  revisionCount: number;
  feedbackDraft: string;
  confirmedAt?: string;
  rejectedAt?: string;
  projectCreated: boolean;
  createdProjectName?: string;
  sections: {
    label: string;
    value: string;
  }[];
  milestones: string[];
}

export type PlanFlowAction =
  | { type: "update_feedback"; feedback: string }
  | { type: "request_changes"; feedback: string }
  | { type: "reject_plan" }
  | { type: "confirm_plan" }
  | { type: "create_project"; projectName?: string }
  | { type: "reset" };

export function createInitialPlanFlowState(): PlanFlowState {
  return {
    stage: "draft",
    title: "计划草案",
    summary: "先把目标收敛成普通用户能确认的范围。真实能力会在后端接入后再执行。",
    projectName: "二手交易平台 MVP",
    revisionCount: 0,
    feedbackDraft: "",
    projectCreated: false,
    sections: [
      { label: "目标", value: "完成商品发布、搜索、聊天和订单闭环的第一版可用产品。" },
      { label: "边界", value: "暂不做支付、风控和复杂运营后台，避免第一版范围失控。" },
      { label: "交付", value: "先生成前端页面、后端接口清单、数据模型和验收路径。" },
    ],
    milestones: [
      "确认 MVP 范围和不做事项",
      "创建正式项目并绑定项目会话",
      "后续接入真实后端后再推进执行",
    ],
  };
}

export function applyPlanFlowAction(state: PlanFlowState, action: PlanFlowAction): PlanFlowState {
  switch (action.type) {
    case "update_feedback":
      return {
        ...state,
        feedbackDraft: action.feedback,
      };

    case "request_changes": {
      const feedback = action.feedback.trim();
      return {
        ...state,
        stage: "changes_requested",
        feedbackDraft: feedback || "请缩小第一版范围，并重新整理执行顺序。",
        revisionCount: state.revisionCount + 1,
      };
    }

    case "reject_plan":
      return {
        ...state,
        stage: "rejected",
        rejectedAt: "刚刚",
      };

    case "confirm_plan":
      return {
        ...state,
        stage: "confirmed",
        confirmedAt: "刚刚",
      };

    case "create_project": {
      const projectName = action.projectName?.trim() || state.projectName;
      return {
        ...state,
        stage: "created",
        projectCreated: true,
        createdProjectName: projectName,
      };
    }

    case "reset":
      return createInitialPlanFlowState();
  }
}

export const planFlowPreviewStates = {
  draft: createInitialPlanFlowState(),
  changesRequested: applyPlanFlowAction(createInitialPlanFlowState(), {
    type: "request_changes",
    feedback: "第一版先不要做支付；把范围收敛到商品、搜索、聊天。",
  }),
  rejected: applyPlanFlowAction(createInitialPlanFlowState(), { type: "reject_plan" }),
  confirmed: applyPlanFlowAction(createInitialPlanFlowState(), { type: "confirm_plan" }),
  created: applyPlanFlowAction(
    applyPlanFlowAction(createInitialPlanFlowState(), { type: "confirm_plan" }),
    { type: "create_project", projectName: "二手交易平台 MVP" },
  ),
} as const;
