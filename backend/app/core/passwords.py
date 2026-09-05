from pwdlib import PasswordHash


_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a plaintext password using the recommended password hashing scheme."""
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against its stored password hash."""
    return _password_hash.verify(password, password_hash)
