"""Fake Azure Cost Management query responses, duck-typed to the real SDK shape
(QueryResult with .columns[i].name and .rows as list-of-lists, values looked up
by column name rather than position - see map_cost_response)."""

from types import SimpleNamespace

COLUMNS = [
    SimpleNamespace(name="Cost"),
    SimpleNamespace(name="UsageDate"),
    SimpleNamespace(name="ResourceId"),
    SimpleNamespace(name="ChargeType"),
    SimpleNamespace(name="Currency"),
]

VM_RESOURCE_ID = (
    "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-prod"
    "/providers/Microsoft.Compute/virtualMachines/vm-web-01"
)

# Cost Management often returns a different case for the resource group segment
# than Resource Graph does - used to test the case-insensitive resource match.
VM_RESOURCE_ID_DIFFERENT_CASE = VM_RESOURCE_ID.replace("rg-prod", "RG-Prod")


def make_response(*rows: list) -> SimpleNamespace:
    return SimpleNamespace(columns=COLUMNS, rows=[list(row) for row in rows])


# [Cost, UsageDate, ResourceId, ChargeType, Currency]
RESOURCE_ATTRIBUTABLE_ROW = [12.3456, 20260915, VM_RESOURCE_ID_DIFFERENT_CASE, "Usage", "USD"]
MARKETPLACE_ROW = [5.00, 20260915, "", "Usage", "USD"]
SUPPORT_ROW = [50.00, 20260915, "", "Purchase", "USD"]

RESPONSE_MIXED = make_response(RESOURCE_ATTRIBUTABLE_ROW, MARKETPLACE_ROW, SUPPORT_ROW)
