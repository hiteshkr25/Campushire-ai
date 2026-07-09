import enum
import uuid
from datetime import datetime, timezone


class AuthError(Exception):
    """Base authentication error."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class InvalidCredentialsError(AuthError):
    def __init__(self, message="Invalid email or password."):
        super().__init__(message, status_code=401)


class AccountInactiveError(AuthError):
    def __init__(self, message="Your account has been deactivated."):
        super().__init__(message, status_code=403)


class AccountUnverifiedError(AuthError):
    def __init__(self, message="Please verify your account before signing in."):
        super().__init__(message, status_code=403)


class RegistrationError(AuthError):
    pass


class PasswordResetError(AuthError):
    pass


class PasswordChangeError(AuthError):
    pass


class StudentServiceError(Exception):
    """Base student domain error."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DriveNotFoundError(StudentServiceError):
    def __init__(self, message="Drive not found."):
        super().__init__(message, status_code=404)


class ApplicationNotFoundError(StudentServiceError):
    def __init__(self, message="Application not found."):
        super().__init__(message, status_code=404)


class ApplicationError(StudentServiceError):
    pass


class EligibilityError(ApplicationError):
    pass
