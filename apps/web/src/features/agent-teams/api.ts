import { requestJson } from "../../lib/http";
import type {
  TeamControlCenterSnapshot,
  TeamControlCenterUpdateRequest,
} from "./types";

export function fetchTeamControlCenterSnapshot(input: { projectId: string }) {
  return requestJson<TeamControlCenterSnapshot>(
    `/projects/${input.projectId}/team-control-center`,
  );
}

export function updateTeamControlCenterSnapshot(input: {
  projectId: string;
  payload: TeamControlCenterUpdateRequest;
}) {
  return requestJson<TeamControlCenterSnapshot>(
    `/projects/${input.projectId}/team-control-center`,
    {
      method: "PUT",
      body: JSON.stringify(input.payload),
    },
  );
}
