from dataclasses import dataclass

# Azure Resource Graph's power state code for a VM that has been stopped from
# within the guest OS (or via API "stop") but NOT deallocated - Azure keeps
# the compute allocation reserved and keeps billing for it. Only
# "PowerState/deallocated" actually stops the meter. Deliberately matched
# exactly, not "any non-running state" - "PowerState/deallocating",
# "PowerState/starting" etc are transitional and not the billing-waste state
# this check is after.
STOPPED_NOT_DEALLOCATED_POWER_STATE_CODE = "PowerState/stopped"


@dataclass
class IdleCheckResult:
    is_flagged: bool
    detail: str


def detect_unattached_disk(raw_metadata: dict) -> IdleCheckResult:
    """Flag a managed disk with diskState == "Unattached".

    The task's original assumption was that Resource Graph's `managedBy`
    field (null/absent = unattached) would drive this check, but the
    existing Task 2 connector's query doesn't project `managedBy` at all, and
    a real synced disk's raw_metadata was checked directly and confirmed it
    isn't there. `properties.diskState` is present instead, and is Azure's
    own explicit attachment-state field (values include "Attached",
    "Unattached", "Reserved", "ActiveSAS", etc) - a cleaner, more direct
    signal than `managedBy` would have been anyway, so this check uses that
    instead of guessing at a field name that isn't actually synced.
    """
    properties = raw_metadata.get("properties") or {}
    disk_state = properties.get("diskState")
    if disk_state is None:
        return IdleCheckResult(
            False, "diskState is not present in the synced metadata; attachment state can't be determined."
        )
    if disk_state == "Unattached":
        return IdleCheckResult(True, "diskState is 'Unattached'.")
    return IdleCheckResult(False, f"diskState is '{disk_state}', not 'Unattached'.")


def detect_unused_public_ip(raw_metadata: dict) -> IdleCheckResult:
    """Flag a public IP with no `properties.ipConfiguration` - confirmed
    against a real synced public IP's raw_metadata to match exactly as the
    task described (present with an `id` when associated to a NIC, and this
    check's fixtures exercise the absent case)."""
    properties = raw_metadata.get("properties") or {}
    ip_configuration = properties.get("ipConfiguration")
    if ip_configuration:
        return IdleCheckResult(False, "ipConfiguration is present; the IP is associated with a resource.")
    return IdleCheckResult(True, "ipConfiguration is null/absent; the IP is not associated with any resource.")


def _get_power_state_code(properties: dict) -> str | None:
    extended = properties.get("extended")
    if not isinstance(extended, dict):
        return None
    instance_view = extended.get("instanceView")
    if not isinstance(instance_view, dict):
        return None
    power_state = instance_view.get("powerState")
    if not isinstance(power_state, dict):
        return None
    return power_state.get("code")


def detect_stopped_not_deallocated_vm(raw_metadata: dict) -> IdleCheckResult:
    """Flag a VM whose power state is 'stopped' but not 'deallocated'.

    `properties.extended.instanceView.powerState.code` is already present in
    what the existing Task 2 Resource Graph connector syncs - confirmed
    against a real synced VM's raw_metadata (it showed "PowerState/running")
    - so no connector change or live per-VM API call is needed; see
    results.txt for the fuller investigation. A VM with no power state
    recorded is excluded rather than flagged/cleared on a guess, same
    "insufficient data -> exclude" principle as forecasting/rightsizing.
    """
    properties = raw_metadata.get("properties") or {}
    code = _get_power_state_code(properties)
    if code is None:
        return IdleCheckResult(
            False,
            "No power state found in synced metadata "
            "(properties.extended.instanceView.powerState.code missing); excluded rather than guessed.",
        )
    if code == STOPPED_NOT_DEALLOCATED_POWER_STATE_CODE:
        return IdleCheckResult(
            True, f"powerState.code is '{code}' - stopped but not deallocated, still billing for compute."
        )
    return IdleCheckResult(False, f"powerState.code is '{code}', not the stopped-but-not-deallocated state.")
