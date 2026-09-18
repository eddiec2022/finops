from app.services.non_prod_heuristics import detect_non_prod_by_name, detect_non_prod_by_tag

# --- tag heuristic -----------------------------------------------------------


def test_detect_non_prod_by_tag_matches_environment_key():
    result = detect_non_prod_by_tag({"environment": "dev"})

    assert result.matched is True
    assert "environment" in result.detail


def test_detect_non_prod_by_tag_matches_env_key_case_insensitively():
    result = detect_non_prod_by_tag({"Env": "STAGING"})

    assert result.matched is True


def test_detect_non_prod_by_tag_does_not_match_production_value():
    result = detect_non_prod_by_tag({"environment": "production"})

    assert result.matched is False


def test_detect_non_prod_by_tag_does_not_match_unrelated_tags():
    result = detect_non_prod_by_tag({"owner": "platform-team", "costCenter": "1234"})

    assert result.matched is False


def test_detect_non_prod_by_tag_empty_tags_does_not_match():
    assert detect_non_prod_by_tag({}).matched is False
    assert detect_non_prod_by_tag(None).matched is False


def test_detect_non_prod_by_tag_matches_each_documented_value():
    for value in ("dev", "test", "staging", "sandbox"):
        assert detect_non_prod_by_tag({"environment": value}).matched is True


# --- naming heuristic ----------------------------------------------------------


def test_detect_non_prod_by_name_matches_dev_substring():
    result = detect_non_prod_by_name("nise-dev")

    assert result.matched is True
    assert "dev" in result.detail


def test_detect_non_prod_by_name_case_insensitive():
    result = detect_non_prod_by_name("APP-STAGING-01")

    assert result.matched is True


def test_detect_non_prod_by_name_does_not_match_production_name():
    result = detect_non_prod_by_name("prod-api-01")

    assert result.matched is False


def test_detect_non_prod_by_name_matches_each_documented_keyword():
    for keyword in ("dev", "test", "staging", "sandbox", "demo"):
        assert detect_non_prod_by_name(f"app-{keyword}-01").matched is True


def test_detect_non_prod_by_name_missing_name_does_not_match():
    assert detect_non_prod_by_name(None).matched is False
    assert detect_non_prod_by_name("").matched is False
