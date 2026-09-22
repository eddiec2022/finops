from dataclasses import dataclass

# EBS's own explicit attachment-state field - direct analogue of Azure's
# diskState check. "in-use" is the attached state; "available"/"creating"/
# "deleting"/"error" are the others, but only "available" means unattached.
UNATTACHED_VOLUME_STATE = "available"

# EC2's own explicit instance lifecycle state. Unlike Azure's "stopped but not
# deallocated" (which keeps billing compute), a stopped EC2 instance does NOT
# bill for compute - only for anything still attached (EBS volumes, an
# Elastic IP no longer covered by a running-instance exemption). Flagged as
# a real analogue of Task 9's check per the task's own instruction, but the
# detail text below is accurate about what's actually still billing, not a
# copy-paste of Azure's compute-waste framing.
STOPPED_INSTANCE_STATE = "stopped"


@dataclass
class IdleCheckResult:
    is_flagged: bool
    detail: str


def detect_unattached_ebs_volume(raw_metadata: dict) -> IdleCheckResult:
    """Flag an EBS volume with state == "available" (unattached).

    Mirrors azure_idle_resource_detection.detect_unattached_disk - reads the
    `state` field aws_inventory._enrich_ebs_volumes already stores in
    raw_metadata during sync, not a live call at recommendation time.
    """
    state = raw_metadata.get("state")
    if state is None:
        return IdleCheckResult(
            False, "state is not present in the synced metadata; attachment state can't be determined."
        )
    if state == UNATTACHED_VOLUME_STATE:
        return IdleCheckResult(True, f"state is '{state}' (unattached).")
    return IdleCheckResult(False, f"state is '{state}', not '{UNATTACHED_VOLUME_STATE}'.")


def detect_unassociated_elastic_ip(raw_metadata: dict) -> IdleCheckResult:
    """Flag an Elastic IP with no InstanceId/NetworkInterfaceId association.

    Mirrors azure_idle_resource_detection.detect_unused_public_ip. Reads the
    `associated` boolean aws_inventory._enrich_elastic_ips stores.
    """
    associated = raw_metadata.get("associated")
    if associated is None:
        return IdleCheckResult(
            False, "associated is not present in the synced metadata; association state can't be determined."
        )
    if associated:
        return IdleCheckResult(False, "associated with an instance or network interface.")
    return IdleCheckResult(True, "not associated with any instance or network interface - still billed hourly while unattached.")


def detect_stopped_ec2_instance(raw_metadata: dict) -> IdleCheckResult:
    """Flag an EC2 instance whose state is 'stopped'.

    Real difference from Azure's equivalent check, stated plainly rather than
    glossed over: a stopped EC2 instance does NOT bill for compute (unlike
    Azure's "stopped but not deallocated", which does) - the waste here is
    whatever's still attached and billing (EBS volumes, an Elastic IP that
    loses its running-instance fee exemption once stopped), not idle compute
    itself. Still a real, worth-flagging state - a stopped instance is easy to
    forget about - just not the same kind of waste as Azure's check.
    """
    state = raw_metadata.get("state")
    if state is None:
        return IdleCheckResult(False, "state is not present in the synced metadata; instance state can't be determined.")
    if state == STOPPED_INSTANCE_STATE:
        return IdleCheckResult(
            True,
            f"state is '{state}' - not billing compute, but any attached EBS volumes or an Elastic IP "
            "(which loses its running-instance fee exemption once stopped) still are.",
        )
    return IdleCheckResult(False, f"state is '{state}', not '{STOPPED_INSTANCE_STATE}'.")
