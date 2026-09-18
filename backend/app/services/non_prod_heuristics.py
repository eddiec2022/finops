from dataclasses import dataclass

# Per GOV-001: tags, naming convention, OR usage pattern - any one signal is
# sufficient, none are certainties. These lists are exactly what the task
# specified, not expanded - checked against the real synced resources' tags
# first (all empty in the real dev subscription, so the tag heuristic has
# nothing to match there today; that's a fact about the current data, not a
# reason to skip building the check).
ENV_TAG_KEYS = ("environment", "env")
NON_PROD_ENV_TAG_VALUES = frozenset({"dev", "test", "staging", "sandbox"})
NON_PROD_NAME_KEYWORDS = ("dev", "test", "staging", "sandbox", "demo")


@dataclass
class NonProdSignalResult:
    matched: bool
    detail: str


def detect_non_prod_by_tag(tags: dict) -> NonProdSignalResult:
    for key, value in (tags or {}).items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        if key.lower() in ENV_TAG_KEYS and value.lower() in NON_PROD_ENV_TAG_VALUES:
            return NonProdSignalResult(True, f"tag '{key}'='{value}' indicates a non-production environment")
    return NonProdSignalResult(False, "no environment-indicating tag found")


def detect_non_prod_by_name(name: str | None) -> NonProdSignalResult:
    lowered = (name or "").lower()
    for keyword in NON_PROD_NAME_KEYWORDS:
        if keyword in lowered:
            return NonProdSignalResult(True, f"resource name contains '{keyword}'")
    return NonProdSignalResult(False, "resource name doesn't match a non-production naming pattern")
