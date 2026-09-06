from types import SimpleNamespace

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