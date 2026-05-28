import { useMutation } from "@tanstack/react-query";

import { createProjectDirectorSession } from "./api";

export function useCreateProjectDirectorSession() {
  return useMutation({
    mutationFn: createProjectDirectorSession,
  });
}
