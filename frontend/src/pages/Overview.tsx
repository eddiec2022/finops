import { useEffect, useState } from "react";
import { getResources } from "../api/client";
import type { ResourceListItem } from "../api/types";
import { Breadcrumb, type BreadcrumbSegment } from "../components/Breadcrumb";
import { DrillList } from "../components/DrillList";
import { SpendPanel } from "../components/SpendPanel";
import { listProvider, middleLevelLabel, resourceLabel, summarizeResourceGroups } from "../lib/groupResources";

type DrillPath =
  | { level: "subscription" }
  | { level: "resource-group"; resourceGroup: string }
  | { level: "resource"; resourceGroup: string; resource: ResourceListItem };

type ResourceListState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; resources: ResourceListItem[] };

export function Overview() {
  const [path, setPath] = useState<DrillPath>({ level: "subscription" });
  const [resourceList, setResourceList] = useState<ResourceListState>({ status: "loading" });

  const resourceGroupFilter = path.level !== "subscription" ? path.resourceGroup : undefined;

  useEffect(() => {
    // Resource level has nothing further to list - the selected resource is
    // already known from the click that navigated here, so skip the fetch.
    if (path.level === "resource") return;

    setResourceList({ status: "loading" });
    getResources(resourceGroupFilter ? { resourceGroup: resourceGroupFilter } : undefined)
      .then((response) => setResourceList({ status: "ready", resources: response.resources }))
      .catch(() => setResourceList({ status: "error" }));
  }, [path.level, resourceGroupFilter]);

  const breadcrumbSegments: BreadcrumbSegment[] = [
    {
      label: "Overview",
      onClick: path.level !== "subscription" ? () => setPath({ level: "subscription" }) : undefined,
    },
  ];
  if (path.level === "resource-group" || path.level === "resource") {
    breadcrumbSegments.push({
      label: path.resourceGroup,
      onClick:
        path.level === "resource" ? () => setPath({ level: "resource-group", resourceGroup: path.resourceGroup }) : undefined,
    });
  }
  if (path.level === "resource") {
    breadcrumbSegments.push({ label: resourceLabel(path.resource) });
  }

  return (
    <div>
      <h1 className="mb-2 text-2xl font-semibold">Overview</h1>
      <Breadcrumb segments={breadcrumbSegments} />

      {path.level === "resource" && (
        <div className="mb-6 rounded-xl bg-white p-6 shadow-sm">
          <p className="text-sm text-stone-500">Resource</p>
          <p className="mt-1 text-lg font-semibold text-brand-dark">{resourceLabel(path.resource)}</p>
          <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <dt className="text-stone-400">Type</dt>
            <dd className="text-stone-700">{path.resource.resource_type}</dd>
            <dt className="text-stone-400">Region</dt>
            <dd className="text-stone-700">{path.resource.region ?? "—"}</dd>
            <dt className="text-stone-400">{middleLevelLabel(path.resource.provider)}</dt>
            <dd className="text-stone-700">{path.resource.resource_group ?? "—"}</dd>
          </dl>
        </div>
      )}

      <div className="mb-6">
        <SpendPanel
          resourceGroup={path.level === "resource-group" ? path.resourceGroup : undefined}
          resourceId={path.level === "resource" ? path.resource.resource_id : undefined}
          emptyStateDescription={
            path.level === "resource-group"
              ? `${middleLevelLabel(listProvider(resourceList.status === "ready" ? resourceList.resources : []))} "${path.resourceGroup}" hasn't synced enough days of cost data to show a spend trend or forecast yet.`
              : path.level === "resource"
                ? `${resourceLabel(path.resource)} hasn't synced enough days of cost data to show a spend trend or forecast yet.`
                : undefined
          }
        />
      </div>

      {path.level === "subscription" && (
        <>
          {resourceList.status === "loading" && <p className="text-stone-500">Loading resource groups…</p>}
          {resourceList.status === "error" && (
            <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">
              Couldn't load resource groups. Try refreshing.
            </div>
          )}
          {resourceList.status === "ready" && (
            <DrillList
              title={middleLevelLabel(listProvider(resourceList.resources), { plural: true })}
              emptyMessage={`No ${middleLevelLabel(listProvider(resourceList.resources), { plural: true }).toLowerCase()} have synced yet.`}
              items={summarizeResourceGroups(resourceList.resources).map((group) => ({
                key: group.resourceGroup,
                primary: group.resourceGroup,
                secondary: `${group.resourceCount} resource${group.resourceCount === 1 ? "" : "s"}`,
                onClick: () => setPath({ level: "resource-group", resourceGroup: group.resourceGroup }),
              }))}
            />
          )}
        </>
      )}

      {path.level === "resource-group" && (
        <>
          {resourceList.status === "loading" && <p className="text-stone-500">Loading resources…</p>}
          {resourceList.status === "error" && (
            <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">
              Couldn't load resources. Try refreshing.
            </div>
          )}
          {resourceList.status === "ready" && (
            <DrillList
              title={`Resources in ${path.resourceGroup}`}
              emptyMessage={`No resources found in this ${middleLevelLabel(listProvider(resourceList.resources)).toLowerCase()}.`}
              items={resourceList.resources.map((resource) => ({
                key: resource.resource_id,
                primary: resourceLabel(resource),
                secondary: resource.resource_type,
                onClick: () => setPath({ level: "resource", resourceGroup: path.resourceGroup, resource }),
              }))}
            />
          )}
        </>
      )}
    </div>
  );
}
