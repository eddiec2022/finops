import type { ResourceListItem } from "../api/types";

export interface ResourceGroupSummary {
  resourceGroup: string;
  resourceCount: number;
}

/**
 * Groups a flat resource list into unique resource groups with counts, sorted
 * alphabetically. Resources with no resource_group are excluded - there's
 * nothing to drill into for them.
 */
export function summarizeResourceGroups(resources: ResourceListItem[]): ResourceGroupSummary[] {
  const counts = new Map<string, number>();
  for (const resource of resources) {
    if (!resource.resource_group) continue;
    counts.set(resource.resource_group, (counts.get(resource.resource_group) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([resourceGroup, resourceCount]) => ({ resourceGroup, resourceCount }))
    .sort((a, b) => a.resourceGroup.localeCompare(b.resourceGroup));
}

/** Best-available display label for a resource: name, then ARM id, then internal id. */
export function resourceLabel(resource: ResourceListItem): string {
  return resource.name ?? resource.external_resource_id ?? resource.resource_id;
}
