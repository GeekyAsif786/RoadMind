from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.auth import (
    ROLE_ADMIN,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    check_role,
)


def make_user(role: str):
    return SimpleNamespace(
        role=role,
        is_active=True,
    )


def test_allowed_role_passes():
    user = make_user(ROLE_ADMIN)

    assert check_role(
        user,
        {ROLE_ADMIN},
    ) is user


def test_disallowed_role_returns_403():
    user = make_user(ROLE_VIEWER)

    with pytest.raises(HTTPException) as exc:
        check_role(
            user,
            {ROLE_ADMIN},
        )

    assert exc.value.status_code == 403


def test_operator_allowed_for_operator_action():
    user = make_user(ROLE_OPERATOR)

    assert check_role(
        user,
        {ROLE_OPERATOR, ROLE_ADMIN},
    ) is user


def test_viewer_rejected_from_operator_action():
    user = make_user(ROLE_VIEWER)

    with pytest.raises(HTTPException) as exc:
        check_role(
            user,
            {ROLE_OPERATOR, ROLE_ADMIN},
        )

    assert exc.value.status_code == 403

from app.core.auth import (
    ROLE_ADMIN,
    ROLE_OPERATOR,
    ROLE_VIEWER,
    check_role,
    require_admin,
    require_authenticated_user,
    require_operator_or_admin,
)
from app.models.domain import User


def make_user(role: str) -> User:
    user = MagicMock(spec=User)
    user.role = role
    user.is_active = True
    return user


@pytest.mark.parametrize("role", [ROLE_VIEWER, ROLE_OPERATOR, ROLE_ADMIN])
def test_authenticated_user_allows_all_roles(role):
    user = make_user(role)

    result = require_authenticated_user(user)

    assert result is user


@pytest.mark.parametrize("role", [ROLE_OPERATOR, ROLE_ADMIN])
def test_operator_or_admin_allows_operator_and_admin(role):
    user = make_user(role)

    result = require_operator_or_admin(user)

    assert result is user


def test_operator_or_admin_rejects_viewer():
    user = make_user(ROLE_VIEWER)

    with pytest.raises(HTTPException) as exc:
        require_operator_or_admin(user)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Insufficient permissions"


def test_admin_allows_admin():
    user = make_user(ROLE_ADMIN)

    result = require_admin(user)

    assert result is user


@pytest.mark.parametrize("role", [ROLE_VIEWER, ROLE_OPERATOR])
def test_admin_rejects_non_admin(role):
    user = make_user(role)

    with pytest.raises(HTTPException) as exc:
        require_admin(user)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Insufficient permissions"   

def test_role_policy_matrix():
    assert check_role(make_user(ROLE_VIEWER), {ROLE_VIEWER}) .role == ROLE_VIEWER
    assert check_role(make_user(ROLE_OPERATOR), {ROLE_OPERATOR, ROLE_ADMIN}).role == ROLE_OPERATOR
    assert check_role(make_user(ROLE_ADMIN), {ROLE_OPERATOR, ROLE_ADMIN}).role == ROLE_ADMIN