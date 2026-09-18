from app.services.idle_resource_detection import (
    detect_stopped_not_deallocated_vm,
    detect_unattached_disk,
    detect_unused_public_ip,
)


# --- unattached disk --------------------------------------------------------


def test_detect_unattached_disk_flags_unattached_state():
    result = detect_unattached_disk({"properties": {"diskState": "Unattached"}})

    assert result.is_flagged is True
    assert "unattached" in result.detail.lower()


def test_detect_unattached_disk_does_not_flag_attached_state():
    result = detect_unattached_disk({"properties": {"diskState": "Attached"}})

    assert result.is_flagged is False


def test_detect_unattached_disk_does_not_flag_other_non_attached_states():
    # "Reserved" (about to be attached) and "ActiveSAS" (export/snapshot in
    # progress) are not "Attached" but also aren't wasted capacity the same
    # way "Unattached" is - only the exact "Unattached" value flags.
    assert detect_unattached_disk({"properties": {"diskState": "Reserved"}}).is_flagged is False
    assert detect_unattached_disk({"properties": {"diskState": "ActiveSAS"}}).is_flagged is False


def test_detect_unattached_disk_missing_diskstate_is_not_flagged():
    # Missing entirely is different from a confirmed "Unattached" value -
    # must not be flagged on a guess.
    result = detect_unattached_disk({"properties": {}})

    assert result.is_flagged is False
    assert "not present" in result.detail.lower()


def test_detect_unattached_disk_missing_properties_is_not_flagged():
    result = detect_unattached_disk({})

    assert result.is_flagged is False


# --- unused public IP --------------------------------------------------------


def test_detect_unused_public_ip_flags_missing_ip_configuration():
    result = detect_unused_public_ip({"properties": {}})

    assert result.is_flagged is True
    assert "not associated" in result.detail.lower()


def test_detect_unused_public_ip_does_not_flag_when_associated():
    result = detect_unused_public_ip(
        {"properties": {"ipConfiguration": {"id": "/subscriptions/.../ipConfigurations/ipconfig1"}}}
    )

    assert result.is_flagged is False


def test_detect_unused_public_ip_flags_null_ip_configuration():
    result = detect_unused_public_ip({"properties": {"ipConfiguration": None}})

    assert result.is_flagged is True


def test_detect_unused_public_ip_missing_properties_is_flagged():
    result = detect_unused_public_ip({})

    assert result.is_flagged is True


# --- stopped-but-not-deallocated VM ------------------------------------------


def _power_state_metadata(code: str) -> dict:
    return {"properties": {"extended": {"instanceView": {"powerState": {"code": code}}}}}


def test_detect_stopped_not_deallocated_vm_flags_stopped():
    result = detect_stopped_not_deallocated_vm(_power_state_metadata("PowerState/stopped"))

    assert result.is_flagged is True
    assert "stopped but not deallocated" in result.detail.lower()


def test_detect_stopped_not_deallocated_vm_does_not_flag_running():
    result = detect_stopped_not_deallocated_vm(_power_state_metadata("PowerState/running"))

    assert result.is_flagged is False


def test_detect_stopped_not_deallocated_vm_does_not_flag_properly_deallocated():
    # This is the state that DOES stop billing - must not be flagged.
    result = detect_stopped_not_deallocated_vm(_power_state_metadata("PowerState/deallocated"))

    assert result.is_flagged is False


def test_detect_stopped_not_deallocated_vm_does_not_flag_transitional_states():
    assert detect_stopped_not_deallocated_vm(_power_state_metadata("PowerState/deallocating")).is_flagged is False
    assert detect_stopped_not_deallocated_vm(_power_state_metadata("PowerState/starting")).is_flagged is False


def test_detect_stopped_not_deallocated_vm_missing_power_state_is_excluded_not_flagged():
    result = detect_stopped_not_deallocated_vm({"properties": {}})

    assert result.is_flagged is False
    assert "no power state found" in result.detail.lower()


def test_detect_stopped_not_deallocated_vm_missing_properties_is_excluded_not_flagged():
    result = detect_stopped_not_deallocated_vm({})

    assert result.is_flagged is False
