from app.core.device_credentials import (
    generate_device_credential,
    hash_device_credential,
    verify_device_credential,
)


def test_generated_device_credential_can_be_verified():
    secret = generate_device_credential()
    hashed = hash_device_credential(secret)

    assert verify_device_credential(secret, hashed)