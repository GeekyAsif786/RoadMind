import io
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.passwords import verify_password
from app.db import create_admin
from app.db.create_admin import (
    AdminProvisioningError,
    create_first_admin,
    ensure_interactive_terminal,
    ensure_migrations_current,
    validate_email,
    validate_password,
    validate_username,
)
from app.db.session import SessionLocal, engine
from app.models.domain import User

PASSWORD = "Correct-Horse-42!"
BACKEND_ROOT = Path(__file__).resolve().parents[1]


class FakeTTY(io.StringIO):
    def isatty(self) -> bool:
        return True


@pytest.fixture
def isolated_db():
    """
    A session whose commits become SAVEPOINT releases inside an outer
    transaction that is always rolled back, so no row (and no table lock)
    survives the test.
    """
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def empty_users(isolated_db):
    if create_admin.any_user_exists(isolated_db):
        pytest.skip("users table is not empty in the test database")
    return isolated_db


def _user_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User))


def _current_migrations(monkeypatch):
    import app.core.startup as startup

    monkeypatch.setattr(
        startup,
        "get_migration_status",
        lambda engine: {"status": "current", "database_revision": "x", "head_revision": "x"},
    )


# --- environment / database validation -------------------------------------


@pytest.mark.parametrize(
    ("stdin", "stdout"),
    [
        (io.StringIO(), FakeTTY()),
        (FakeTTY(), io.StringIO()),
        (io.StringIO(), io.StringIO()),
    ],
    ids=["stdin-piped", "stdout-redirected", "no-tty"],
)
def test_requires_interactive_terminal(stdin, stdout):
    with pytest.raises(AdminProvisioningError, match="interactive terminal"):
        ensure_interactive_terminal(stdin, stdout)


def test_interactive_terminal_accepted():
    ensure_interactive_terminal(FakeTTY(), FakeTTY())


def test_run_refuses_without_tty_before_touching_database():
    engine_mock = MagicMock()
    session_factory = MagicMock()

    with pytest.raises(AdminProvisioningError, match="interactive terminal"):
        create_admin.run(
            engine=engine_mock,
            session_factory=session_factory,
            stdin=io.StringIO(),
            stdout=io.StringIO(),
        )

    engine_mock.connect.assert_not_called()
    session_factory.assert_not_called()


def test_migrations_current_against_real_database():
    ensure_migrations_current(engine)


def test_refuses_when_migrations_not_current(monkeypatch):
    import app.core.startup as startup

    monkeypatch.setattr(
        startup,
        "get_migration_status",
        lambda engine: {
            "status": "out_of_date",
            "database_revision": "",
            "head_revision": "e5c1e605dfd1",
        },
    )

    with pytest.raises(AdminProvisioningError, match="alembic upgrade head"):
        ensure_migrations_current(MagicMock())


def test_database_unreachable_is_reported_cleanly(monkeypatch):
    import app.core.startup as startup

    def unreachable(engine):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(startup, "get_migration_status", unreachable)

    with pytest.raises(AdminProvisioningError, match="Cannot connect to the database"):
        ensure_migrations_current(MagicMock())


def test_run_refuses_outdated_schema_before_prompting(monkeypatch):
    import app.core.startup as startup

    monkeypatch.setattr(
        startup,
        "get_migration_status",
        lambda engine: {"status": "out_of_date", "database_revision": "", "head_revision": "h"},
    )
    session_factory = MagicMock()
    read = MagicMock()
    read_secret = MagicMock()

    with pytest.raises(AdminProvisioningError, match="migrations are not current"):
        create_admin.run(
            engine=MagicMock(),
            session_factory=session_factory,
            read=read,
            read_secret=read_secret,
            stdin=FakeTTY(),
            stdout=FakeTTY(),
        )

    session_factory.assert_not_called()
    read.assert_not_called()
    read_secret.assert_not_called()


def test_password_cannot_be_passed_on_command_line():
    """Arguments are ignored and a non-TTY invocation is refused outright."""
    result = subprocess.run(
        [sys.executable, "-m", "app.db.create_admin", "--password", PASSWORD],
        cwd=BACKEND_ROOT,
        input="",
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 1
    assert "interactive terminal" in result.stderr
    assert PASSWORD not in result.stdout + result.stderr


def _run_cli(**env_overrides):
    import os

    env = {**os.environ, **env_overrides}
    return subprocess.run(
        [sys.executable, "-m", "app.db.create_admin"],
        cwd=BACKEND_ROOT,
        env=env,
        input="",
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_production_guard_failure_exits_cleanly():
    result = _run_cli(ENVIRONMENT="production", API_KEY="dev-insecure-key-change-me")

    assert result.returncode == 1
    assert result.stderr.startswith("Error: Refusing to start in production")
    assert "Traceback" not in result.stderr
    assert "dev-insecure-key-change-me" not in result.stderr


def test_invalid_setting_exits_cleanly_without_echoing_value():
    result = _run_cli(SESSION_TTL_SECONDS="not-a-number-secret")

    assert result.returncode == 1
    assert "Invalid configuration (session_ttl_seconds:" in result.stderr
    assert "Traceback" not in result.stderr
    assert "not-a-number-secret" not in result.stderr


def test_invalid_database_url_exits_cleanly():
    result = _run_cli(DATABASE_URL="not a url")

    assert result.returncode == 1
    assert "DATABASE_URL is not a valid database URL." in result.stderr
    assert "Traceback" not in result.stderr


def test_main_reports_expected_errors_on_stderr(monkeypatch, capsys):
    def misconfigured():
        raise AdminProvisioningError("Refusing to start in production with ENABLE_AUTH=false.")

    monkeypatch.setattr(create_admin, "load_database", misconfigured)

    assert create_admin.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Error: Refusing to start in production with ENABLE_AUTH=false.\n"


def test_main_does_not_swallow_unexpected_errors(monkeypatch):
    def broken(**kwargs):
        raise ZeroDivisionError("programming error")

    monkeypatch.setattr(create_admin, "load_database", lambda: (MagicMock(), MagicMock()))
    monkeypatch.setattr(create_admin, "run", broken)

    with pytest.raises(ZeroDivisionError):
        create_admin.main()


def test_load_database_maps_production_guard_error(monkeypatch):
    import app.core.config as config

    def guard():
        raise RuntimeError("Refusing to start in production with SESSION_COOKIE_SECURE=false.")

    monkeypatch.setattr(config, "get_settings", guard)

    with pytest.raises(AdminProvisioningError, match="SESSION_COOKIE_SECURE=false"):
        create_admin.load_database()


# --- input validation -------------------------------------------------------


@pytest.mark.parametrize("username", ["admin", "ops.admin", "a_b-c", "x" * 80, "  admin  "])
def test_valid_usernames(username):
    assert validate_username(username) == username.strip()


@pytest.mark.parametrize(
    "username",
    ["", "ab", "x" * 81, "admin@example.com", "has space", "-admin", "admin.", "ädmin"],
)
def test_invalid_usernames(username):
    with pytest.raises(ValueError):
        validate_username(username)


def test_valid_email_is_normalized():
    assert validate_email("  admin@example.com ") == "admin@example.com"


@pytest.mark.parametrize("email", ["", "not-an-email", "a@", "@example.com", "a" * 250 + "@x.com"])
def test_invalid_emails(email):
    with pytest.raises(ValueError):
        validate_email(email)


@pytest.mark.parametrize("password", ["x" * 12, "x" * 128, PASSWORD])
def test_valid_password_lengths(password):
    validate_password(password, username="admin", email="admin@example.com")


@pytest.mark.parametrize("password", ["", "x" * 11, "x" * 129, " " * 12])
def test_invalid_passwords(password):
    with pytest.raises(ValueError) as exc:
        validate_password(password, username="admin", email="admin@example.com")
    if password.strip():
        assert password not in str(exc.value)


@pytest.mark.parametrize("password", ["administrator", "ADMIN@EXAMPLE.COM"])
def test_password_must_differ_from_identity(password):
    with pytest.raises(ValueError, match="same as the username or email"):
        validate_password(password, username="administrator", email="admin@example.com")


# --- creation -----------------------------------------------------------------


def test_creates_first_admin_with_hashed_password(empty_users):
    db = empty_users

    user = create_first_admin(
        db, username="first-admin", email="first-admin@example.com", password=PASSWORD
    )

    stored = db.scalar(select(User).where(User.id == user.id))
    assert stored.username == "first-admin"
    assert stored.email == "first-admin@example.com"
    assert stored.role == "admin"
    assert stored.is_active is True
    assert stored.password_hash != PASSWORD
    assert PASSWORD not in stored.password_hash
    assert stored.password_hash.startswith("$argon2")
    assert verify_password(PASSWORD, stored.password_hash)
    assert not verify_password(PASSWORD + "x", stored.password_hash)
    assert _user_count(db) == 1


def test_refuses_when_any_user_exists(empty_users):
    db = empty_users
    db.add(User(username="existing-viewer", email="viewer@example.com", password_hash="x", role="viewer"))
    db.commit()

    with pytest.raises(AdminProvisioningError, match="not empty"):
        create_first_admin(db, username="second-admin", email="second@example.com", password=PASSWORD)

    assert _user_count(db) == 1
    assert db.scalar(select(User).where(User.username == "second-admin")) is None


def test_run_refuses_when_users_exist_before_prompting(empty_users, monkeypatch):
    db = empty_users
    db.add(User(username="existing-admin", email="existing@example.com", password_hash="x", role="admin"))
    db.commit()
    _current_migrations(monkeypatch)
    read = MagicMock()
    read_secret = MagicMock()

    with pytest.raises(AdminProvisioningError, match="not empty"):
        create_admin.run(
            engine=engine,
            session_factory=lambda: db,
            read=read,
            read_secret=read_secret,
            stdin=FakeTTY(),
            stdout=FakeTTY(),
        )

    read.assert_not_called()
    read_secret.assert_not_called()


def test_run_interactive_flow_does_not_echo_credentials(empty_users, monkeypatch):
    db = empty_users
    _current_migrations(monkeypatch)
    answers = iter(["bad name", "roadmind-admin", "roadmind-admin@example.com"])
    secrets = iter(["short", PASSWORD, PASSWORD + "typo", PASSWORD, PASSWORD])
    prompts: list[str] = []
    stdout, stderr = FakeTTY(), io.StringIO()

    def read(prompt):
        prompts.append(prompt)
        return next(answers)

    def read_secret(prompt):
        prompts.append(prompt)
        return next(secrets)

    user = create_admin.run(
        engine=engine,
        session_factory=lambda: db,
        read=read,
        read_secret=read_secret,
        stdin=FakeTTY(),
        stdout=stdout,
        stderr=stderr,
    )

    assert user.role == "admin"
    assert verify_password(PASSWORD, user.password_hash)
    assert prompts == [
        "Username: ",
        "Username: ",
        "Email: ",
        "Password: ",
        "Password: ",
        "Confirm password: ",
        "Password: ",
        "Confirm password: ",
    ]
    output = stdout.getvalue() + stderr.getvalue()
    assert "Passwords do not match." in output
    assert PASSWORD not in output
    assert "short" not in output


def test_run_aborts_after_repeated_invalid_input(empty_users, monkeypatch):
    db = empty_users
    _current_migrations(monkeypatch)

    with pytest.raises(AdminProvisioningError, match="Too many invalid attempts"):
        create_admin.run(
            engine=engine,
            session_factory=lambda: db,
            read=lambda prompt: "x",
            read_secret=MagicMock(),
            stdin=FakeTTY(),
            stdout=FakeTTY(),
            stderr=io.StringIO(),
        )

    assert _user_count(db) == 0


# --- transaction safety -------------------------------------------------------


def test_failed_commit_rolls_back_and_leaves_no_user(empty_users, monkeypatch):
    db = empty_users

    def failing_commit():
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(db, "commit", failing_commit)

    with pytest.raises(RuntimeError, match="simulated commit failure"):
        create_first_admin(db, username="rollback-admin", email="rollback@example.com", password=PASSWORD)

    monkeypatch.undo()
    assert _user_count(db) == 0


def test_integrity_error_is_rolled_back_and_reported():
    db = MagicMock()
    db.scalar.return_value = False
    db.flush.side_effect = IntegrityError("INSERT", {}, Exception("duplicate key"))

    with pytest.raises(AdminProvisioningError, match="already in use"):
        create_first_admin(db, username="dup-admin", email="dup@example.com", password=PASSWORD)

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_table_is_locked_before_emptiness_check():
    db = MagicMock()
    calls: list[str] = []
    db.execute.side_effect = lambda statement: calls.append(str(statement))
    db.scalar.side_effect = lambda statement: calls.append("exists-check") or False

    create_first_admin(db, username="lock-admin", email="lock@example.com", password=PASSWORD)

    assert calls[0] == "LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"
    assert calls[1] == "exists-check"
    db.commit.assert_called_once()


def _wait_for_blocked_users_lock(timeout: float = 10.0) -> bool:
    statement = text(
        "SELECT count(*) FROM pg_locks "
        "WHERE relation = 'users'::regclass AND NOT granted"
    )
    deadline = time.monotonic() + timeout
    with engine.connect() as observer:
        while time.monotonic() < deadline:
            if observer.execute(statement).scalar_one():
                return True
            observer.rollback()
            time.sleep(0.05)
    return False


def test_concurrent_bootstrap_creates_only_one_admin():
    """
    A second bootstrap that starts while the first holds the users lock must
    wait, then observe the committed admin and refuse. Uses real commits on
    separate connections; created rows are deleted afterwards.
    """
    first = SessionLocal()
    usernames = ["race-admin-a", "race-admin-b"]
    outcome: dict[str, object] = {}

    def second_bootstrap():
        second = SessionLocal()
        try:
            outcome["user"] = create_first_admin(
                second, username="race-admin-b", email="race-b@example.com", password=PASSWORD
            )
        except Exception as exc:
            outcome["error"] = exc
        finally:
            second.close()

    try:
        if create_admin.any_user_exists(first):
            pytest.skip("users table is not empty in the test database")
        first.rollback()

        first.execute(create_admin._LOCK_USERS_TABLE)
        create_admin.ensure_no_users(first)

        worker = threading.Thread(target=second_bootstrap)
        worker.start()
        assert _wait_for_blocked_users_lock(), "second bootstrap should block on the users lock"
        assert worker.is_alive()

        first.add(User(username="race-admin-a", email="race-a@example.com", password_hash="x", role="admin"))
        first.commit()

        worker.join(timeout=10)
        assert not worker.is_alive()
        assert isinstance(outcome.get("error"), AdminProvisioningError)
        assert "user" not in outcome
        assert _user_count(first) == 1
    finally:
        first.rollback()
        first.execute(delete(User).where(User.username.in_(usernames)))
        first.commit()
        first.close()
