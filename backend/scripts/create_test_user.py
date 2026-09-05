from sqlalchemy import select

from app.core.passwords import hash_password
from app.db.session import SessionLocal
from app.models.domain import User


USERNAME = "admin"
EMAIL = "admin@roadmind.local"
PASSWORD = "AdminTest123!"


def main() -> None:
    db = SessionLocal()

    try:
        existing = db.scalar(
            select(User).where(
                (User.username == USERNAME) | (User.email == EMAIL)
            )
        )

        if existing is not None:
            print(f"User already exists: {existing.username}")
            return

        user = User(
            username=USERNAME,
            email=EMAIL,
            password_hash=hash_password(PASSWORD),
            role="admin",
            is_active=True,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        print(f"Created user: {user.username}")
        print(f"User ID: {user.id}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
