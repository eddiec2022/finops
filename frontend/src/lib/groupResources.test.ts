import { describe, expect, it } from "vitest";
import type { ResourceListItem } from "../api/types";
import { resourceLabel, summarizeResourceGroups } from "./groupResources";

function makeResource(overrides: Partial<ResourceListItem>): ResourceListItem {
  return {
    resource_id: "id-1",
    external_resource_id: "/subscriptions/x/resourceGroups/rg-a/providers/Microsoft.Compute/virtualMachines/vm-1",
    name: "vm-1",
    resource_group: "rg-a",
    resource_type: "microsoft.compute/virtualmachines",
    region: "eastus",
    ...overrides,
  };
}

describe("summarizeResourceGroups", () => {
  it("groups resources by resource_group and counts them", () => {
    const resources = [
      makeResource({ resource_id: "1", resource_group: "rg-b" }),
      makeResource({ resource_id: "2", resource_group: "rg-a" }),
      makeResource({ resource_id: "3", resource_group: "rg-a" }),
    ];

    expect(summarizeResourceGroups(resources)).toEqual([
      { resourceGroup: "rg-a", resourceCount: 2 },
      { resourceGroup: "rg-b", resourceCount: 1 },
    ]);
  });

  it("excludes resources with no resource_group", () => {
    const resources = [makeResource({ resource_id: "1", resource_group: null })];

    expect(summarizeResourceGroups(resources)).toEqual([]);
  });

  it("returns an empty list for no resources", () => {
    expect(summarizeResourceGroups([])).toEqual([]);
  });
});

describe("resourceLabel", () => {
  it("prefers name when present", () => {
    expect(resourceLabel(makeResource({ name: "vm-web-01" }))).toBe("vm-web-01");
  });

  it("falls back to external_resource_id when name is missing", () => {
    const resource = makeResource({ name: null, external_resource_id: "/subscriptions/x/vm-1" });
    expect(resourceLabel(resource)).toBe("/subscriptions/x/vm-1");
  });

  it("falls back to internal resource_id when both are missing", () => {
    const resource = makeResource({ name: null, external_resource_id: null, resource_id: "internal-id" });
    expect(resourceLabel(resource)).toBe("internal-id");
  });
});
