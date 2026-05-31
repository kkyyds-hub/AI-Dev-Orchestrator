export type ProjectDirectorSourceCarrier = {
  source_plan_version_id?: string | null;
  source_draft_id?: string | null;
};

export type ProjectDirectorSourceReadback = {
  sourcePlanVersionId: string;
  sourceDraftIds: string[];
};

type CollectProjectDirectorSourceInput = {
  items: Array<ProjectDirectorSourceCarrier | null | undefined>;
};

export function collectProjectDirectorSource(
  input: CollectProjectDirectorSourceInput,
): ProjectDirectorSourceReadback | null {
  const sourcePlanVersionId = firstNonEmpty(
    input.items.map((item) => item?.source_plan_version_id),
  );

  if (!sourcePlanVersionId) {
    return null;
  }

  const sourceDraftIds = uniqueNonEmpty(
    input.items.map((item) => item?.source_draft_id),
  );

  return {
    sourcePlanVersionId,
    sourceDraftIds,
  };
}

function firstNonEmpty(values: Array<string | null | undefined>) {
  return uniqueNonEmpty(values)[0] ?? null;
}

function uniqueNonEmpty(values: Array<string | null | undefined>) {
  const seen = new Set<string>();
  const result: string[] = [];

  for (const rawValue of values) {
    const value = rawValue?.trim();
    if (!value || seen.has(value)) {
      continue;
    }
    seen.add(value);
    result.push(value);
  }

  return result;
}
