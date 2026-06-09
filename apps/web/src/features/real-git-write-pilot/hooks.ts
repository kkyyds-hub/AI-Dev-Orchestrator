import { useMutation } from "@tanstack/react-query";

import { recordRealGitWritePilotApprovalReadback } from "./api";

export function useRecordRealGitWritePilotApprovalReadback() {
  return useMutation({
    mutationFn: recordRealGitWritePilotApprovalReadback,
  });
}
