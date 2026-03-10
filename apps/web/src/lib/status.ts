export type BadgeTone = "neutral" | "info" | "success" | "warning" | "danger";

export function mapTaskStatusTone(status: string): BadgeTone {
  switch (status) {
    case "completed":
      return "success";
    case "running":
      return "info";
    case "paused":
      return "neutral";
    case "waiting_human":
      return "warning";
    case "failed":
      return "danger";
    case "blocked":
      return "warning";
    default:
      return "neutral";
  }
}

export function mapRunStatusTone(status: string): BadgeTone {
  switch (status) {
    case "succeeded":
      return "success";
    case "running":
      return "info";
    case "failed":
      return "danger";
    case "cancelled":
      return "warning";
    default:
      return "neutral";
  }
}

export function mapLogLevelTone(level: string): BadgeTone {
  switch (level) {
    case "error":
      return "danger";
    case "warning":
      return "warning";
    case "debug":
      return "neutral";
    default:
      return "info";
  }
}

export function mapFailureCategoryTone(category: string | null): BadgeTone {
  switch (category) {
    case "verification_configuration_failed":
    case "daily_budget_exceeded":
    case "session_budget_exceeded":
    case "retry_limit_exceeded":
      return "warning";
    case "verification_failed":
    case "execution_failed":
      return "danger";
    default:
      return "neutral";
  }
}

export function mapQualityGateTone(
  qualityGatePassed: boolean | null,
): BadgeTone {
  if (qualityGatePassed === true) {
    return "success";
  }

  if (qualityGatePassed === false) {
    return "danger";
  }

  return "neutral";
}
