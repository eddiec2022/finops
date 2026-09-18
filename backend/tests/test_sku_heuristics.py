import pytest

from app.services.sku_heuristics import suggest_app_service_tier, suggest_vm_sku


def test_suggest_vm_sku_halves_core_count_within_same_family():
    result = suggest_vm_sku("Standard_D4s_v7")

    assert result.suggested_sku == "Standard_D2s_v7"
    assert result.cores_reduction_fraction == 0.5
    assert "heuristic" in result.note.lower()


def test_suggest_vm_sku_no_version_suffix():
    result = suggest_vm_sku("Standard_B2ms")

    assert result.suggested_sku == "Standard_B1ms"
    assert result.cores_reduction_fraction == 0.5


def test_suggest_vm_sku_odd_core_count_rounds_down():
    result = suggest_vm_sku("Standard_D3_v2")

    assert result.suggested_sku == "Standard_D1_v2"
    assert result.cores_reduction_fraction == pytest.approx(2 / 3)


def test_suggest_vm_sku_already_smallest_size_gives_no_suggestion():
    result = suggest_vm_sku("Standard_D1s_v3")

    assert result.suggested_sku is None
    assert result.cores_reduction_fraction is None
    assert "smallest" in result.note.lower()


def test_suggest_vm_sku_constrained_core_pattern_gives_no_suggestion_not_a_bad_guess():
    # "E8-4s" doesn't match the simple <family><cores><suffix> pattern (embedded
    # dash) - must decline to suggest rather than mangle it.
    result = suggest_vm_sku("Standard_E8-4s_v5")

    assert result.suggested_sku is None
    assert result.cores_reduction_fraction is None
    assert "e8-4s" in result.note.lower()


def test_suggest_vm_sku_missing_sku_gives_no_suggestion():
    result = suggest_vm_sku(None)

    assert result.suggested_sku is None
    assert result.cores_reduction_fraction is None


def test_suggest_vm_sku_unparseable_pattern_gives_no_suggestion():
    result = suggest_vm_sku("CustomWeirdName")

    assert result.suggested_sku is None
    assert result.cores_reduction_fraction is None


def test_suggest_app_service_tier_never_guesses_a_specific_tier():
    result = suggest_app_service_tier("S2")

    assert result.suggested_sku is None
    assert result.cores_reduction_fraction is None
    assert "tier" in result.note.lower()
