import { useQuery } from "@tanstack/react-query";

import { fetchWorkerSlots } from "./api";

export function useWorkerSlots() {
  return useQuery({
    queryKey: ["worker-slots"],
    queryFn: fetchWorkerSlots,
    refetchInterval: 5000,
  });
}
