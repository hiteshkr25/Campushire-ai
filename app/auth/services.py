import uuid
from datetime import datetime, timezone

from flask import current_app, url_for
from flask_login import login_user as flask_login_user
from flask_login import logout_user as flask_logout_user

from app.exceptions import (
    AccountInactiveError,
    AccountUnverifiedError,
    AuthError,
    InvalidCredentialsError,
    PasswordChangeError,
    PasswordResetError,
    RegistrationError,
)
from app.extensions import bcrypt, db
from app.models.audit import AuditLog
from app.models.college import Branch, College
from app.models.company import Company, Recruiter
from app.models.enums import AuditAction, ProfileStatus, UserRole, VerificationStatus
from app.models.student import Student
from app.models.user import User
from app.utils.constants import ROLE_DASHBOARD_ENDPOINTS, SELF_REGISTRATION_ROLES
from app.utils.email_sender import send_password_reset_email
from app.utils.token_utils import generate_password_reset_token, verify_password_reset_token


class AuthService:
    @staticmethod
    def hash_password(password):
        return bcrypt.generate_password_hash(
            password,
            rounds=current_app.config.get("BCRYPT_LOG_ROUNDS", 12),
        ).decode("utf-8")

    @staticmethod
    def check_password(password_hash, password):
        return bcrypt.check_password_hash(password_hash, password)

    @staticmethod
    def get_dashboard_url(user):
        endpoint = ROLE_DASHBOARD_ENDPOINTS.get(user.role, "main.index")
        return url_for(endpoint)

    @staticmethod
    def _log_audit(user, action, entity_type, entity_id=None, old_values=None, new_values=None, ip_address=None, user_agent=None):
        log = AuditLog(
            user_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.session.add(log)

    @classmethod
    def register_student(
        cls,
        *,
        email,
        password,
        college_code,
        branch_code,
        enrollment_number,
        first_name,
        last_name,
        batch,
        graduation_year,
        phone=None,
    ):
        email = email.strip().lower()
        college = College.query.filter_by(code=college_code.upper(), is_active=True).first()
        if not college:
            raise RegistrationError("Invalid or inactive college code.")

        branch = Branch.query.filter_by(
            college_id=college.id,
            code=branch_code.upper(),
            is_active=True,
        ).first()
        if not branch:
            raise RegistrationError("Invalid or inactive branch code for this college.")

        if User.query.filter_by(email=email).first():
            raise RegistrationError("An account with this email already exists.")

        if Student.query.filter_by(
            college_id=college.id,
            enrollment_number=enrollment_number.strip(),
        ).first():
            raise RegistrationError("This enrollment number is already registered.")

        user = User(
            email=email,
            password_hash=cls.hash_password(password),
            role=UserRole.STUDENT,
            is_active=True,
            is_verified=True,
        )
        student = Student(
            user=user,
            college=college,
            branch=branch,
            enrollment_number=enrollment_number.strip(),
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            phone=phone.strip() if phone else None,
            batch=batch.strip(),
            graduation_year=graduation_year,
            profile_status=ProfileStatus.PENDING_VERIFICATION,
        )
        db.session.add(user)
        db.session.add(student)
        db.session.commit()
        return user

    @classmethod
    def register_recruiter(
        cls,
        *,
        email,
        password,
        company_name,
        first_name,
        last_name,
        designation=None,
        phone=None,
    ):
        email = email.strip().lower()
        company_name = company_name.strip()

        if User.query.filter_by(email=email).first():
            raise RegistrationError("An account with this email already exists.")

        company = Company.query.filter(
            db.func.lower(Company.name) == company_name.lower()
        ).first()
        if not company:
            company = Company(
                name=company_name,
                contact_email=email,
                verification_status=VerificationStatus.PENDING,
                is_active=True,
            )
            db.session.add(company)

        user = User(
            email=email,
            password_hash=cls.hash_password(password),
            role=UserRole.RECRUITER,
            is_active=True,
            is_verified=False,
        )
        recruiter = Recruiter(
            user=user,
            company=company,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            designation=designation.strip() if designation else None,
            phone=phone.strip() if phone else None,
        )
        db.session.add(user)
        db.session.add(recruiter)
        db.session.commit()
        return user

    @classmethod
    def authenticate(cls, email, password, *, ip_address=None, user_agent=None):
        email = email.strip().lower()
        user = User.query.filter_by(email=email).first()

        if not user or not cls.check_password(user.password_hash, password):
            cls._log_audit(
                user,
                AuditAction.LOGIN_FAILED,
                "user",
                entity_id=user.id if user else None,
                new_values={"email": email},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            db.session.commit()
            raise InvalidCredentialsError()

        if not user.is_active:
            raise AccountInactiveError()

        if user.role == UserRole.RECRUITER and not user.is_verified:
            raise AccountUnverifiedError(
                "Your recruiter account is pending admin approval."
            )

        return user

    @classmethod
    def login(cls, user, *, remember=False, ip_address=None, user_agent=None):
        user.last_login_at = datetime.now(timezone.utc)
        cls._log_audit(
            user,
            AuditAction.LOGIN,
            "user",
            entity_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.session.commit()
        flask_login_user(user, remember=remember)
        return user

    @classmethod
    def logout(cls, user, *, ip_address=None, user_agent=None):
        if user and user.is_authenticated:
            cls._log_audit(
                user,
                AuditAction.LOGOUT,
                "user",
                entity_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            db.session.commit()
        flask_logout_user()

    @classmethod
    def request_password_reset(cls, email, *, ip_address=None, user_agent=None):
        email = email.strip().lower()
        user = User.query.filter_by(email=email, is_active=True).first()

        if user:
            token = generate_password_reset_token(user)
            send_password_reset_email(user, token)
            cls._log_audit(
                user,
                AuditAction.UPDATE,
                "user",
                entity_id=user.id,
                new_values={"action": "password_reset_requested"},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            db.session.commit()

        return True

    @classmethod
    def reset_password(cls, token, new_password, *, ip_address=None, user_agent=None):
        user = verify_password_reset_token(token)
        if not user:
            raise PasswordResetError("Invalid or expired reset link.")

        old_hash_prefix = user.password_hash[:32]
        user.password_hash = cls.hash_password(new_password)
        cls._log_audit(
            user,
            AuditAction.UPDATE,
            "user",
            entity_id=user.id,
            old_values={"password_changed": True, "hash_prefix": old_hash_prefix},
            new_values={"password_changed": True},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.session.commit()
        return user

    @classmethod
    def change_password(cls, user, current_password, new_password, *, ip_address=None, user_agent=None):
        if not cls.check_password(user.password_hash, current_password):
            raise PasswordChangeError("Current password is incorrect.")

        if current_password == new_password:
            raise PasswordChangeError("New password must be different from the current password.")

        user.password_hash = cls.hash_password(new_password)
        cls._log_audit(
            user,
            AuditAction.UPDATE,
            "user",
            entity_id=user.id,
            new_values={"password_changed": True},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.session.commit()
        return user

    @staticmethod
    def can_self_register(role):
        return role in SELF_REGISTRATION_ROLES

    @staticmethod
    def load_user_by_id(user_id):
        try:
            uid = uuid.UUID(str(user_id))
        except (ValueError, AttributeError):
            return None
        return db.session.get(User, uid)
