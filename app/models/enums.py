import enum


class UserRole(enum.Enum):
    STUDENT = "student"
    TPO = "tpo"
    RECRUITER = "recruiter"
    ADMIN = "admin"


class ProfileStatus(enum.Enum):
    INCOMPLETE = "incomplete"
    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class VerificationStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DriveStatus(enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    REGISTRATION_CLOSED = "registration_closed"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class LocationType(enum.Enum):
    ON_CAMPUS = "on_campus"
    OFF_CAMPUS = "off_campus"
    VIRTUAL = "virtual"
    HYBRID = "hybrid"


class EligibilityRuleType(enum.Enum):
    MIN_CGPA = "min_cgpa"
    MAX_CGPA = "max_cgpa"
    MAX_BACKLOGS = "max_backlogs"
    MIN_GRADUATION_YEAR = "min_graduation_year"
    MAX_GRADUATION_YEAR = "max_graduation_year"
    ALLOWED_BATCH = "allowed_batch"
    REQUIRED_SKILL = "required_skill"
    GENDER = "gender"
    CUSTOM = "custom"


class EligibilityOperator(enum.Enum):
    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"


class ApplicationStatus(enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    INTERVIEW_IN_PROGRESS = "interview_in_progress"
    SELECTED = "selected"
    OFFERED = "offered"
    PLACED = "placed"
    NOT_SELECTED = "not_selected"


class RoundType(enum.Enum):
    APTITUDE = "aptitude"
    TECHNICAL = "technical"
    CODING = "coding"
    GROUP_DISCUSSION = "group_discussion"
    HR = "hr"
    MANAGERIAL = "managerial"
    OTHER = "other"


class RoundResultStatus(enum.Enum):
    SCHEDULED = "scheduled"
    PASSED = "passed"
    FAILED = "failed"
    ON_HOLD = "on_hold"
    ABSENT = "absent"
    DISQUALIFIED = "disqualified"


class ScheduleStatus(enum.Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"
    NO_SHOW = "no_show"


class OfferStatus(enum.Enum):
    DRAFT = "draft"
    EXTENDED = "extended"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    REVOKED = "revoked"
    EXPIRED = "expired"


class NotificationType(enum.Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    REMINDER = "reminder"
    ANNOUNCEMENT = "announcement"


class AnnouncementAudience(enum.Enum):
    ALL = "all"
    STUDENTS = "students"
    TPO = "tpo"
    RECRUITERS = "recruiters"
    ADMINS = "admins"


class ParseStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditAction(enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    STATUS_CHANGE = "status_change"
    EXPORT = "export"
    UPLOAD = "upload"
    DOWNLOAD = "download"
