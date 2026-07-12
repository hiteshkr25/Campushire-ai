from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import CITEXT, UUID

from app.extensions import db
from app.models.base import BaseModel
from app.models.enums import UserRole


class User(UserMixin, BaseModel):
    __tablename__ = "users"
    __table_args__ = (
        db.UniqueConstraint("email", name="uq_users_email"),
        db.Index("idx_users_role", "role"),
        db.Index("idx_users_is_active", "is_active"),
        db.Index("idx_users_created_at", "created_at"),
    )

    email = db.Column(CITEXT, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole, name="user_role", values_callable=lambda x: [e.value for e in x]), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    last_login_at = db.Column(db.DateTime(timezone=True))
    college_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("colleges.id", ondelete="SET NULL"),
        nullable=True,
    )
    college = db.relationship(
        "College",
        backref=db.backref("users", lazy="dynamic"),
    )

    student_profile = db.relationship(
        "Student",
        backref="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="[Student.user_id]",
    )
    recruiter_profile = db.relationship(
        "Recruiter",
        backref="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="[Recruiter.user_id]",
    )
    tpo_profile = db.relationship(
        "TpoAdmin",
        backref="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="[TpoAdmin.user_id]",
    )
    notifications = db.relationship(
        "Notification",
        backref="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    announcements_created = db.relationship(
        "Announcement",
        backref="author",
        foreign_keys="Announcement.created_by",
        passive_deletes=True,
        lazy="dynamic",
    )
    audit_logs = db.relationship(
        "AuditLog",
        backref="user",
        passive_deletes=True,
        lazy="dynamic",
    )
    verified_students = db.relationship(
        "Student",
        backref="verifier",
        foreign_keys="Student.verified_by",
        passive_deletes=True,
        lazy="dynamic",
    )
    verified_companies = db.relationship(
        "Company",
        backref="verifier",
        foreign_keys="Company.verified_by",
        passive_deletes=True,
        lazy="dynamic",
    )

    def get_id(self):
        return str(self.id)

    @property
    def role_value(self):
        return self.role.value if self.role else None

    def to_dict(self, exclude=None, include=None, exclude_relationships=True):
        default_exclude = {"password_hash"}
        exclude = set(exclude or []) | default_exclude
        return super().to_dict(
            exclude=exclude,
            include=include,
            exclude_relationships=exclude_relationships,
        )

    def __repr__(self):
        return f"<User {self.email} ({self.role_value})>"
