"""
Interactive first-administrator bootstrap.

Creates the very first Web Admin account in an empty ``users`` table. It is a
one-time bootstrap, not a general user-creation mechanism: it refuses to run
once any user exists, whatever that user's role.

Usage (inside the backend container, after ``alembic upgrade head``):

    docker compose exec backend python -m app.db.create_admin

The command must be run from an interactive terminal. Passwords are read with
``getpass`` only; they are never accepted as arguments, environment variables,
or piped input, and are never printed or logged.
"""

import getpass
import re
import sys
from collections.abc import Callable
from typing import TextIO

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import Engine, exists, select, text
from sqlalchemy.exc import ArgumentError, IntegrityError, OperationalError
from sqlalchemy.orm import Session

# Only modules that do not load settings at import time are imported here, so
# configuration errors surface in main() rather than as an import traceback.
# app.core.auth and app.db.session read settings on import; see load_database()
# and create_first_admin().
from app.core.passwords import hash_password
from app.models.domain import User

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 80  # users.username is VARCHAR(80)
EMAIL_MAX_LENGTH = 255  # users.email is VARCHAR(255)
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128  # matches LoginRequest.password max_length

# Letters, digits, '.', '_' and '-', starting and ending with a letter or digit.
# '@' is excluded so a username can never be mistaken for an email at login.
_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")
_EMAIL_ADAPTER = TypeAdapter(EmailStr)

# Blocks concurrent INSERTs into users (and a second bootstrap taking the same
# lock) until this transaction ends, so two simultaneous runs cannot both see
# an empty table and each create an administrator. Plain reads, including
# logins, are not blocked.
_LOCK_USERS_TABLE = text("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE")

_MAX_ATTEMPTS = 3


class AdminProvisioningError(RuntimeError):
    """Raised when the first administrator cannot be created safely."""


def ensure_interactive_terminal(stdin: TextIO, stdout: TextIO) -> None:
    if not (_isatty(stdin) and _isatty(stdout)):
        raise AdminProvisioningError(
            "This command must be run from an interactive terminal (TTY). "
            "Use 'docker compose exec backend python -m app.db.create_admin', "
            "without '-T' and without piping input."
        )


def _isatty(stream: TextIO) -> bool:
    try:
        return stream.isatty()
    except (AttributeError, ValueError):
        return False


def ensure_migrations_current(engine: Engine) -> None:
    from app.core.startup import get_migration_status

    try:
        status = get_migration_status(engine)
    except OperationalError as exc:
        raise AdminProvisioningError(
            "Cannot connect to the database. Check DATABASE_URL and that "
            "PostgreSQL is running."
        ) from exc

    if status["status"] != "current":
        raise AdminProvisioningError(
            "Refusing to create an administrator: database migrations are not "
            f"current (database={status['database_revision'] or 'missing'}, "
            f"head={status['head_revision'] or 'unknown'}). "
            "Run 'alembic upgrade head' first."
        )


def any_user_exists(db: Session) -> bool:
    return bool(db.scalar(select(exists().select_from(User))))


def ensure_no_users(db: Session) -> None:
    if any_user_exists(db):
        raise AdminProvisioningError(
            "Refusing to create an administrator: the users table is not "
            "empty. This command only bootstraps the first account."
        )


def validate_username(value: str) -> str:
    username = value.strip()
    if not USERNAME_MIN_LENGTH <= len(username) <= USERNAME_MAX_LENGTH:
        raise ValueError(
            f"Username must be {USERNAME_MIN_LENGTH}-{USERNAME_MAX_LENGTH} characters."
        )
    if not _USERNAME_PATTERN.fullmatch(username):
        raise ValueError(
            "Username may contain only letters, digits, '.', '_' and '-', and "
            "must start and end with a letter or digit."
        )
    return username


def validate_email(value: str) -> str:
    candidate = value.strip()
    if not candidate or len(candidate) > EMAIL_MAX_LENGTH:
        raise ValueError(f"Email must be 1-{EMAIL_MAX_LENGTH} characters.")
    try:
        email = _EMAIL_ADAPTER.validate_python(candidate)
    except ValidationError:
        raise ValueError("Email address is not valid.") from None
    if len(email) > EMAIL_MAX_LENGTH:
        raise ValueError(f"Email must be 1-{EMAIL_MAX_LENGTH} characters.")
    return email


def validate_password(password: str, *, username: str, email: str) -> None:
    # Error messages describe the rule only; they never echo the password.
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise ValueError(
            f"Password must be {PASSWORD_MIN_LENGTH}-{PASSWORD_MAX_LENGTH} characters."
        )
    if not password.strip():
        raise ValueError("Password must not be only whitespace.")
    lowered = password.lower()
    if lowered in {username.lower(), email.lower()}:
        raise ValueError("Password must not be the same as the username or email.")


def create_first_admin(db: Session, *, username: str, email: str, password: str) -> User:
    """
    Create the first administrator in a single transaction.

    The users table is locked before the emptiness check, so the check and the
    INSERT are atomic with respect to any other writer. Every failure rolls the
    transaction back; nothing is committed unless the account was created.
    """
    from app.core.auth import ROLE_ADMIN

    username = validate_username(username)
    email = validate_email(email)
    validate_password(password, username=username, email=email)

    # Hash before taking the lock to keep the locked window short.
    password_hash = hash_password(password)

    try:
        db.execute(_LOCK_USERS_TABLE)
        ensure_no_users(db)
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role=ROLE_ADMIN,
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AdminProvisioningError(
            "Refusing to create an administrator: the username or email is "
            "already in use."
        ) from exc
    except BaseException:
        db.rollback()
        raise

    # Reload committed state so the returned object stays readable after the
    # caller closes the session.
    db.refresh(user)
    return user


def _prompt_until_valid(
    prompt: str,
    read: Callable[[str], str],
    validate: Callable[[str], str],
    err: TextIO,
) -> str:
    for _ in range(_MAX_ATTEMPTS):
        try:
            return validate(read(prompt))
        except ValueError as exc:
            print(exc, file=err)
    raise AdminProvisioningError("Too many invalid attempts; aborting.")


def _prompt_password(
    read_secret: Callable[[str], str],
    *,
    username: str,
    email: str,
    err: TextIO,
) -> str:
    for _ in range(_MAX_ATTEMPTS):
        password = read_secret("Password: ")
        try:
            validate_password(password, username=username, email=email)
        except ValueError as exc:
            print(exc, file=err)
            continue
        if read_secret("Confirm password: ") != password:
            print("Passwords do not match.", file=err)
            continue
        return password
    raise AdminProvisioningError("Too many invalid attempts; aborting.")


def run(
    *,
    engine: Engine,
    session_factory: Callable[[], Session],
    read: Callable[[str], str] = input,
    read_secret: Callable[[str], str] = getpass.getpass,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> User:
    ensure_interactive_terminal(stdin, stdout)
    ensure_migrations_current(engine)

    db = session_factory()
    try:
        # Fail fast, before asking for a password. create_first_admin repeats
        # this check under a table lock, which is the authoritative one.
        ensure_no_users(db)
        db.rollback()

        print("Create the first RoadMind administrator.", file=stdout)
        username = _prompt_until_valid("Username: ", read, validate_username, stderr)
        email = _prompt_until_valid("Email: ", read, validate_email, stderr)
        password = _prompt_password(read_secret, username=username, email=email, err=stderr)

        return create_first_admin(db, username=username, email=email, password=password)
    finally:
        db.close()


def load_database() -> tuple[Engine, Callable[[], Session]]:
    """
    Load settings and the database engine.

    Expected configuration failures become AdminProvisioningError with a short
    message; anything else propagates with its traceback. Messages never
    include setting values, which may contain secrets.
    """
    from app.core.config import get_settings

    try:
        get_settings()
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise AdminProvisioningError(f"Invalid configuration ({problems}).") from None
    except RuntimeError as exc:
        # Raised by the production configuration guard in app.core.config.
        raise AdminProvisioningError(str(exc)) from None
    except OSError as exc:
        raise AdminProvisioningError(f"Cannot prepare MODEL_DIR: {exc.strerror}.") from None

    try:
        from app.db.session import SessionLocal, engine
    except ArgumentError:
        raise AdminProvisioningError("DATABASE_URL is not a valid database URL.") from None

    return engine, SessionLocal


def main() -> int:
    try:
        engine, session_factory = load_database()
        user = run(engine=engine, session_factory=session_factory)
    except AdminProvisioningError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nAborted; no account was created.", file=sys.stderr)
        return 130

    print(f"Administrator account created (id={user.id}, role={user.role}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
