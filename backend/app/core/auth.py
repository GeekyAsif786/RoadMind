import secrets

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def require_api_key(x_api_key: str = Header(default="")) -> None:
    settings = get_settings()
    if not settings.enable_auth:
        return
    # Constant-time comparison to avoid a timing side-channel that could let an
    # attacker recover the key byte-by-byte. compare_digest requires both
    # operands to be str; the header defaults to "" so it is always a str.
    if not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
