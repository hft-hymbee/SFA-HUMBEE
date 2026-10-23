import json

import pytest

from humbee_sfa.core.settings import SECRETS_JSON_ENV, Settings

SECRET_ENV_NAMES = (
    "HUMBEE_SFA_JWT_SECRET",
    "HUMBEE_SFA_PHONE_HMAC_SECRET",
    "HUMBEE_SFA_PHONE_ENC_KEY",
    "HUMBEE_API_KEY",
)


@pytest.fixture()
def secrets_only_in_json(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for name in SECRET_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def _secrets(**overrides: object) -> str:
    payload: dict[str, object] = {
        "HUMBEE_SFA_JWT_SECRET": "json-jwt-secret-with-at-least-32-bytes",
        "HUMBEE_SFA_PHONE_HMAC_SECRET": "json-phone-hmac-secret",
        "HUMBEE_SFA_PHONE_ENC_KEY": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        "HUMBEE_API_KEY": "json-api-key",
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_secrets_json_supplies_settings(secrets_only_in_json: pytest.MonkeyPatch) -> None:
    secrets_only_in_json.setenv(
        SECRETS_JSON_ENV, _secrets(HUMBEE_SFA_DB_PASSWORD="json-db-password")
    )

    settings = Settings()  # type: ignore[call-arg]

    assert settings.jwt_secret == "json-jwt-secret-with-at-least-32-bytes"
    assert settings.phone_hmac_secret == "json-phone-hmac-secret"
    assert settings.humbee_api_key == "json-api-key"
    assert settings.db_password == "json-db-password"


def test_individual_env_var_wins_over_secrets_json(
    secrets_only_in_json: pytest.MonkeyPatch,
) -> None:
    secrets_only_in_json.setenv(SECRETS_JSON_ENV, _secrets())
    secrets_only_in_json.setenv("HUMBEE_API_KEY", "env-api-key")

    assert Settings().humbee_api_key == "env-api-key"  # type: ignore[call-arg]


def test_secrets_json_decodes_list_given_as_string(
    secrets_only_in_json: pytest.MonkeyPatch,
) -> None:
    secrets_only_in_json.setenv(
        SECRETS_JSON_ENV, _secrets(HUMBEE_SFA_CORS_WEB_ORIGINS='["https://sfa.example.com"]')
    )

    assert Settings().cors_web_origins == ["https://sfa.example.com"]  # type: ignore[call-arg]


def test_invalid_secrets_json_does_not_leak_payload(
    secrets_only_in_json: pytest.MonkeyPatch,
) -> None:
    secrets_only_in_json.setenv(SECRETS_JSON_ENV, '{"HUMBEE_API_KEY": "leaky-value"')

    with pytest.raises(ValueError, match=SECRETS_JSON_ENV) as excinfo:
        Settings()  # type: ignore[call-arg]
    assert "leaky-value" not in str(excinfo.value)


def test_secrets_json_rejects_unknown_keys(secrets_only_in_json: pytest.MonkeyPatch) -> None:
    secrets_only_in_json.setenv(SECRETS_JSON_ENV, _secrets(HUMBEE_SFA_JWT_SECERT="typo"))

    with pytest.raises(ValueError, match="HUMBEE_SFA_JWT_SECERT"):
        Settings()  # type: ignore[call-arg]
