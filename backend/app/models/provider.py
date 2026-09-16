import enum


class Provider(str, enum.Enum):
    """Vendor-agnostic cloud provider identifier, shared across every table.

    Phase 1 only populates AZURE, but the schema must not assume a single
    provider anywhere — see GOV-001 Section 2.
    """

    AZURE = "azure"
    AWS = "aws"
    GCP = "gcp"
