"""CLI script to create a system admin user."""

import getpass
import os
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.auth.services import AuthService
from app.extensions import db
from app.models.enums import UserRole
from app.models.user import User


def create_admin(email, password):
    email = email.strip().lower()
    if User.query.filter_by(email=email).first():
        print(f"User already exists: {email}")
        return False

    user = User(
        email=email,
        password_hash=AuthService.hash_password(password),
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
    )
    db.session.add(user)
    db.session.commit()
    print(f"Admin user created: {email}")
    return True


def main():
    app = create_app(os.environ.get("FLASK_ENV", "development"))
    with app.app_context():
        email = input("Admin email: ").strip()
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.")
            sys.exit(1)
        if not create_admin(email, password):
            sys.exit(1)


if __name__ == "__main__":
    main()
