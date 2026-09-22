from app.services.sku_heuristics import SkuSuggestion

# AWS's standard EC2 instance-size ladder (within a given family, e.g.
# "t3.micro" -> "t3.small" -> "t3.medium" -> ...). Each step is AWS's own
# convention of "roughly double the vCPU/memory of the step before" - unlike
# Azure's SKU naming (a raw core-count baked into the name that this app can
# parse and halve directly, see sku_heuristics.suggest_vm_sku), AWS instance
# types don't encode a number to halve - "large"/"xlarge"/"2xlarge" are
# discrete named steps, so the heuristic here is "step down one size on this
# ladder", not "parse and halve a number".
_SIZE_LADDER = [
    "nano",
    "micro",
    "small",
    "medium",
    "large",
    "xlarge",
    "2xlarge",
    "4xlarge",
    "8xlarge",
    "9xlarge",
    "10xlarge",
    "12xlarge",
    "16xlarge",
    "18xlarge",
    "24xlarge",
    "32xlarge",
    "48xlarge",
]

# Each ladder step is AWS's own "roughly double resources" convention, so a
# one-step-down suggestion is approximately a 50% reduction - used the same
# way sku_heuristics' parsed core-halving informs its own savings-scale
# fraction, just via AWS's naming convention instead of a parsed number.
_STEP_DOWN_REDUCTION_FRACTION = 0.5


def suggest_ec2_instance_type(instance_type: str | None) -> SkuSuggestion:
    """Suggest a smaller EC2 instance type by stepping down one size on AWS's
    standard size ladder, staying within the same family/generation.

    A naming-pattern heuristic only, not a live AWS instance-type availability
    or quota check - mirrors sku_heuristics.suggest_vm_sku's own disclaimer,
    adapted to AWS's discrete-size-name convention instead of Azure's
    parseable core-count.
    """
    if not instance_type:
        return SkuSuggestion(None, "No instance type recorded for this resource; cannot suggest a smaller size.", None)

    if "." not in instance_type:
        return SkuSuggestion(
            None,
            f"Instance type '{instance_type}' does not match the expected <family>.<size> naming pattern; "
            "cannot parse a size.",
            None,
        )

    family, size = instance_type.split(".", 1)
    if size not in _SIZE_LADDER:
        return SkuSuggestion(
            None,
            f"Instance type '{instance_type}' has a size ('{size}') outside the standard "
            "nano..48xlarge steps this heuristic recognizes (e.g. a specialty/metal size) - flagging as a "
            "rightsizing candidate without a specific suggestion rather than force a bad guess.",
            None,
        )

    index = _SIZE_LADDER.index(size)
    if index == 0:
        return SkuSuggestion(
            None, f"Instance type '{instance_type}' is already at the smallest size this heuristic recognizes.", None
        )

    suggested_type = f"{family}.{_SIZE_LADDER[index - 1]}"
    note = (
        f"Heuristic suggestion only: stepped '{instance_type}' down one size on AWS's standard size ladder, "
        f"within the same instance family. This is not a live AWS instance-type availability or quota check - "
        f"'{suggested_type}' may not actually be available in this region/AZ. Verify before resizing."
    )
    return SkuSuggestion(suggested_type, note, _STEP_DOWN_REDUCTION_FRACTION)
