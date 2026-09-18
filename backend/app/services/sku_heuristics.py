import re
from dataclasses import dataclass

# Matches the size-code segment of an Azure VM SKU (e.g. "D4s" in
# "Standard_D4s_v3", "B2ms" in "Standard_B2ms"): letters (family), a digit run
# (core count), then more letters (feature suffix - "s" = premium storage,
# "ms"/"as" etc). Deliberately does NOT match constrained-core / specialty
# patterns with an embedded dash (e.g. "E8-4s") - those fail to match and fall
# through to "no suggestion" rather than being mangled by a naive halving.
_VM_SIZE_RE = re.compile(r"^(?P<family>[A-Za-z]+)(?P<cores>\d+)(?P<suffix>[A-Za-z]*)$")


@dataclass
class SkuSuggestion:
    suggested_sku: str | None
    note: str
    cores_reduction_fraction: float | None


def suggest_vm_sku(sku: str | None) -> SkuSuggestion:
    """Suggest a smaller VM SKU by parsing the core-count component and
    roughly halving it, staying within the same family/suffix/version.

    This is a naming-pattern heuristic only, not a live Azure SKU availability
    or quota check - see the note on the returned SkuSuggestion, which is
    always populated (even when no specific SKU is suggested) so the caller
    never has to guess why.
    """
    if not sku:
        return SkuSuggestion(None, "No SKU recorded for this resource; cannot suggest a smaller size.", None)

    parts = sku.split("_")
    if len(parts) < 2:
        return SkuSuggestion(
            None,
            f"SKU '{sku}' does not match the expected <Tier>_<Size> naming pattern; cannot parse a core count.",
            None,
        )

    size_code = parts[1]
    match = _VM_SIZE_RE.match(size_code)
    if not match:
        return SkuSuggestion(
            None,
            f"SKU '{sku}' has a size component ('{size_code}') that doesn't match the simple "
            "<family><cores><suffix> pattern this heuristic parses (e.g. a constrained-core or "
            "specialty SKU) - flagging as a rightsizing candidate without a specific suggestion "
            "rather than force a bad guess.",
            None,
        )

    cores = int(match.group("cores"))
    if cores <= 1:
        return SkuSuggestion(
            None, f"SKU '{sku}' is already at the smallest core count this heuristic recognizes.", None
        )

    suggested_cores = max(1, cores // 2)
    new_size_code = f"{match.group('family')}{suggested_cores}{match.group('suffix')}"
    parts[1] = new_size_code
    suggested_sku = "_".join(parts)
    note = (
        f"Heuristic suggestion only: parsed the core-count component of '{sku}' and halved it "
        f"within the same series/family/version. This is not a live Azure SKU availability or "
        f"quota check - '{suggested_sku}' may not actually be available in this region. Verify "
        "before resizing."
    )
    return SkuSuggestion(suggested_sku, note, 1 - (suggested_cores / cores))


def suggest_app_service_tier(sku: str | None) -> SkuSuggestion:
    """App Service Plan tier names (e.g. 'S1', 'P2v3', 'B1') encode a
    pricing/feature tier rather than a linear compute unit the way VM series
    sizes do, so there's no clean equivalent of "parse the number, halve it"
    that reliably lands on a valid smaller tier. Per the task's own guidance,
    flag as a rightsizing candidate without a specific suggested tier rather
    than force a bad guess.
    """
    return SkuSuggestion(
        None,
        "App Service tier naming (pricing/feature tier, not a linear compute unit) doesn't map "
        "cleanly to a 'suggest a smaller one' heuristic the way VM SKUs do - flagged as a "
        "rightsizing candidate without a specific suggested tier.",
        None,
    )
