from app.models.enums import UserRole

ROLE_DASHBOARD_ENDPOINTS = {
    UserRole.STUDENT: "student.dashboard",
    UserRole.TPO: "tpo.dashboard",
    UserRole.RECRUITER: "recruiter.dashboard",
    UserRole.ADMIN: "admin.dashboard",
}

SELF_REGISTRATION_ROLES = {UserRole.STUDENT, UserRole.RECRUITER}

PASSWORD_MIN_LENGTH = 8
