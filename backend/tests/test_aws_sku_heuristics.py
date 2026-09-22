from app.services.aws_sku_heuristics import suggest_ec2_instance_type


def test_suggest_ec2_instance_type_steps_down_one_size():
    suggestion = suggest_ec2_instance_type("m5.xlarge")

    assert suggestion.suggested_sku == "m5.large"
    assert suggestion.cores_reduction_fraction == 0.5
    assert "size ladder" in suggestion.note.lower()


def test_suggest_ec2_instance_type_preserves_family_and_generation():
    suggestion = suggest_ec2_instance_type("t3.medium")

    assert suggestion.suggested_sku == "t3.small"


def test_suggest_ec2_instance_type_smallest_size_has_no_suggestion():
    suggestion = suggest_ec2_instance_type("t3.nano")

    assert suggestion.suggested_sku is None
    assert suggestion.cores_reduction_fraction is None
    assert "smallest size" in suggestion.note.lower()


def test_suggest_ec2_instance_type_unrecognized_size_falls_back():
    suggestion = suggest_ec2_instance_type("u-6tb1.metal")

    assert suggestion.suggested_sku is None
    assert suggestion.cores_reduction_fraction is None


def test_suggest_ec2_instance_type_malformed_string():
    suggestion = suggest_ec2_instance_type("not-a-valid-type")

    assert suggestion.suggested_sku is None
    assert "family>.<size" in suggestion.note or "naming pattern" in suggestion.note.lower()


def test_suggest_ec2_instance_type_none_sku():
    suggestion = suggest_ec2_instance_type(None)

    assert suggestion.suggested_sku is None
    assert "no instance type" in suggestion.note.lower()
