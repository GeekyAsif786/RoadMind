from app.core.device_credentials import (
    generate_device_credential,
    hash_device_credential,
    verify_device_credential,
)
import pytest

from app.core.device_credentials import parse_device_credential

def test_generate_device_credential_is_unique():
    first = generate_device_credential()
    second = generate_device_credential()

    assert first != second
    assert len(first) >= 32


def test_hash_and_verify_device_credential():
    credential = generate_device_credential()
    credential_hash = hash_device_credential(credential)

    assert credential_hash != credential
    assert verify_device_credential(credential, credential_hash)


def test_wrong_device_credential_is_rejected():
    credential = generate_device_credential()
    credential_hash = hash_device_credential(credential)

    assert not verify_device_credential(
        "wrong-credential",
        credential_hash,
    )

def test_parse_device_credential():
    credential_id = "dev_test123"
    secret = "secret-value"

    parsed_id, parsed_secret = parse_device_credential(
        f"{credential_id}.{secret}"
    )

    assert parsed_id == credential_id
    assert parsed_secret == secret


def test_parse_device_credential_rejects_invalid_format():
    with pytest.raises(ValueError):
        parse_device_credential("invalid-credential")