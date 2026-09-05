from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.sessions import get_session_store
from app.db.session import get_db
from app.models.domain import User
from app.schemas.auth import LoginRequest, LoginResponse, UserRead
from app.services.auth_service import AuthService

router = APIRouter()

SESSION_COOKIE_PATH = "/"


@router.get("/me", response_model=UserRead)
def me(
    user: User = Depends(get_current_user),
) -> UserRead:
    return UserRead(
        id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
    )

@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    auth_service = AuthService()

    user = auth_service.authenticate_user(
        db=db,
        username_or_email=payload.username_or_email,
        password=payload.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password",
        )

    session_store = get_session_store()
    session_id = session_store.create_session(str(user.id))

    settings = get_settings()

    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path=SESSION_COOKIE_PATH,
    )

    return LoginResponse(
        user=UserRead(
            id=str(user.id),
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
        )
    )