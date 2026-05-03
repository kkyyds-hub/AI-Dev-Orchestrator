import { type FormEvent, useEffect, useState } from "react";

import { MemorySearchEmptyState } from "./components/MemorySearchEmptyState";
import { MemorySearchForm } from "./components/MemorySearchForm";
import { MemorySearchHeader } from "./components/MemorySearchHeader";
import { MemorySearchPromptState } from "./components/MemorySearchPromptState";
import {
  MemorySearchErrorState,
  MemorySearchLoadingState,
} from "./components/MemorySearchQueryState";
import { MemorySearchResults } from "./components/MemorySearchResults";
import { useProjectMemorySearch } from "./hooks";
import type { ProjectMemoryKind } from "./types";

type MemorySearchPanelProps = {
  projectId: string | null;
  projectName: string | null;
  onNavigateToTask?: (taskId: string, options?: { runId?: string | null }) => void;
  onNavigateToDeliverable?: (input: {
    projectId: string;
    deliverableId: string;
  }) => void;
  onNavigateToApproval?: (input: {
    projectId: string;
    approvalId: string;
  }) => void;
};

export function MemorySearchPanel(props: MemorySearchPanelProps) {
  const [draftQuery, setDraftQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [selectedType, setSelectedType] = useState<"all" | ProjectMemoryKind>("all");

  useEffect(() => {
    setDraftQuery("");
    setSubmittedQuery("");
    setSelectedType("all");
  }, [props.projectId]);

  const searchQuery = useProjectMemorySearch({
    projectId: props.projectId,
    query: submittedQuery,
    memoryType: selectedType === "all" ? null : selectedType,
    limit: 8,
    enabled: submittedQuery.trim().length > 0,
  });

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmittedQuery(draftQuery.trim());
  };

  if (!props.projectId) {
    return <MemorySearchEmptyState />;
  }

  const projectId = props.projectId;

  return (
    <section className="space-y-5 rounded-[28px] border border-slate-800 bg-slate-950/70 p-6 shadow-2xl shadow-slate-950/30">
      <MemorySearchHeader />

      <MemorySearchForm
        draftQuery={draftQuery}
        selectedType={selectedType}
        onDraftQueryChange={setDraftQuery}
        onSelectedTypeChange={setSelectedType}
        onSubmit={handleSubmit}
      />

      {!submittedQuery ? (
        <MemorySearchPromptState projectName={props.projectName} />
      ) : searchQuery.isLoading && !searchQuery.data ? (
        <MemorySearchLoadingState />
      ) : searchQuery.isError ? (
        <MemorySearchErrorState message={searchQuery.error.message} />
      ) : (
        <MemorySearchResults
          projectId={projectId}
          submittedQuery={submittedQuery}
          totalMatches={searchQuery.data?.total_matches ?? 0}
          hits={searchQuery.data?.hits ?? []}
          onNavigateToTask={props.onNavigateToTask}
          onNavigateToDeliverable={props.onNavigateToDeliverable}
          onNavigateToApproval={props.onNavigateToApproval}
        />
      )}
    </section>
  );
}
