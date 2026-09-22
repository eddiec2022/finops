from app.services.aws_idle_resource_detection import (
    detect_stopped_ec2_instance,
    detect_unassociated_elastic_ip,
    detect_unattached_ebs_volume,
)


def test_detect_unattached_ebs_volume_flags_available_state():
    result = detect_unattached_ebs_volume({"state": "available"})

    assert result.is_flagged is True
    assert "available" in result.detail


def test_detect_unattached_ebs_volume_does_not_flag_in_use():
    result = detect_unattached_ebs_volume({"state": "in-use"})

    assert result.is_flagged is False


def test_detect_unattached_ebs_volume_missing_state_not_flagged():
    result = detect_unattached_ebs_volume({})

    assert result.is_flagged is False
    assert "not present" in result.detail


def test_detect_unassociated_elastic_ip_flags_unassociated():
    result = detect_unassociated_elastic_ip({"associated": False})

    assert result.is_flagged is True


def test_detect_unassociated_elastic_ip_does_not_flag_associated():
    result = detect_unassociated_elastic_ip({"associated": True})

    assert result.is_flagged is False


def test_detect_unassociated_elastic_ip_missing_field_not_flagged():
    result = detect_unassociated_elastic_ip({})

    assert result.is_flagged is False
    assert "not present" in result.detail


def test_detect_stopped_ec2_instance_flags_stopped():
    result = detect_stopped_ec2_instance({"state": "stopped"})

    assert result.is_flagged is True
    # Real AWS billing nuance stated in the detail, not copied from Azure's
    # "still billing compute" framing - a stopped EC2 instance doesn't.
    assert "not billing compute" in result.detail


def test_detect_stopped_ec2_instance_does_not_flag_running():
    result = detect_stopped_ec2_instance({"state": "running"})

    assert result.is_flagged is False


def test_detect_stopped_ec2_instance_does_not_flag_terminated():
    result = detect_stopped_ec2_instance({"state": "terminated"})

    assert result.is_flagged is False


def test_detect_stopped_ec2_instance_missing_state_not_flagged():
    result = detect_stopped_ec2_instance({})

    assert result.is_flagged is False
    assert "not present" in result.detail
