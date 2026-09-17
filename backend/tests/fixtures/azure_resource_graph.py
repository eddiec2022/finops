"""Representative Azure Resource Graph rows, trimmed to the fields the connector reads."""

VM_ROW = {
    "id": "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-prod"
    "/providers/Microsoft.Compute/virtualMachines/vm-web-01",
    "name": "vm-web-01",
    "type": "microsoft.compute/virtualmachines",
    "location": "eastus",
    "resourceGroup": "rg-prod",
    "tags": {"env": "prod", "owner": "platform-team"},
    "sku": None,
    "properties": {
        "hardwareProfile": {"vmSize": "Standard_D2s_v3"},
        "timeCreated": "2025-01-15T12:00:00Z",
        "provisioningState": "Succeeded",
    },
}

STORAGE_ACCOUNT_ROW = {
    "id": "/subscriptions/11111111-1111-1111-1111-111111111111/resourceGroups/rg-prod"
    "/providers/Microsoft.Storage/storageAccounts/stprodlogs01",
    "name": "stprodlogs01",
    "type": "microsoft.storage/storageaccounts",
    "location": "eastus",
    "resourceGroup": "rg-prod",
    "tags": {"env": "prod"},
    "sku": {"name": "Standard_LRS", "tier": "Standard"},
    "properties": {
        "creationTime": "2024-11-02T09:30:00Z",
        "provisioningState": "Succeeded",
    },
}
