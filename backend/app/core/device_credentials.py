import secrets

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()


def generate_device_credential() -> str:
    return secrets.token_urlsafe(32)


def hash_device_credential(credential: str) -> str:
    return _password_hash.hash(credential)

def parse_device_credential(value: str) -> tuple[str, str]:
    try:
        credential_id, secret = value.split(".", 1)
    except ValueError as exc:
        raise ValueError("Invalid device credential format") from exc

    if not credential_id or not secret:
        raise ValueError("Invalid device credential format")

    return credential_id, secret

def verify_device_credential(
    credential: str,
    credential_hash: str,
) -> bool:
    return _password_hash.verify(credential, credential_hash)