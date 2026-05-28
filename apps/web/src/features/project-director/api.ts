import { requestJson } from "../../lib/http";

import type {
  CreateProjectDirectorSessionInput,
  ProjectDirectorSession,
} from "./types";

export function createProjectDirectorSession(
  input: CreateProjectDirectorSessionInput,
): Promise<ProjectDirectorSession> {
  return requestJson<ProjectDirectorSession>("/project-director/sessions", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
