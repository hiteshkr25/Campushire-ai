from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import deferred

from app.extensions import db
from app.models.base import BaseModel
from app.models.enums import ParseStatus, ProfileStatus


class Student(BaseModel):
    __tablename__ = "students"
    __table_args__ = (
        db.UniqueConstraint("user_id", name="uq_students_user_id"),
        db.UniqueConstraint("college_id", "enrollment_number", name="uq_students_enrollment"),
        db.Index("idx_students_college_id", "college_id"),
        db.Index("idx_students_branch_id", "branch_id"),
        db.Index("idx_students_graduation_year", "graduation_year"),
        db.Index("idx_students_profile_status", "profile_status"),
        db.Index("idx_students_college_batch", "college_id", "batch"),
        db.Index("idx_students_cgpa", "cgpa"),
    )

    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    college_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("colleges.id", ondelete="RESTRICT"),
        nullable=False,
    )
    branch_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    enrollment_number = db.Column(db.String(50), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(20))
    cgpa = db.Column(db.Numeric(4, 2))
    graduation_year = db.Column(db.SmallInteger, nullable=False)
    batch = db.Column(db.String(20), nullable=False)
    semester = db.Column(db.SmallInteger)
    backlogs_count = db.Column(db.SmallInteger, nullable=False, default=0)
    profile_status = db.Column(
        db.Enum(ProfileStatus, name="profile_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ProfileStatus.INCOMPLETE,
    )
    bio = db.Column(db.Text)
    linkedin_url = db.Column(db.String(500))
    github_url = db.Column(db.String(500))
    verified_at = db.Column(db.DateTime(timezone=True))
    verified_by = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="SET NULL"),
    )
    rejection_reason = db.Column(db.Text)
    rejection_count = db.Column(db.Integer, default=0, nullable=False)

    @property
    def reviewed_by(self):
        return self.verified_by

    @property
    def reviewed_at(self):
        return self.verified_at

    @property
    def verifier_name(self):
        if not self.verifier:
            return "System / Auto"
        if self.verifier.role.value == "tpo" and self.verifier.tpo_profile:
            return self.verifier.tpo_profile.full_name
        if self.verifier.role.value == "admin":
            return "Administrator"
        return self.verifier.email


    skills = db.relationship(
        "StudentSkill",
        backref="student",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    projects = db.relationship(
        "StudentProject",
        backref="student",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    certifications = db.relationship(
        "StudentCertification",
        backref="student",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    resumes = db.relationship(
        "Resume",
        backref="student",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="dynamic",
    )
    applications = db.relationship(
        "Application",
        backref="student",
        passive_deletes=True,
        lazy="dynamic",
    )

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def to_dict(self, exclude=None, include=None, exclude_relationships=True):
        data = super().to_dict(
            exclude=exclude,
            include=include,
            exclude_relationships=exclude_relationships,
        )
        data["full_name"] = self.full_name
        return data

    def __repr__(self):
        return f"<Student {self.enrollment_number}: {self.full_name}>"

    def is_profile_complete(self):
        """Return True when all required profile sections are filled."""
        checks = [
            self.first_name,
            self.last_name,
            self.phone,
            self.date_of_birth,
            self.gender,
            self.cgpa is not None,
            self.graduation_year,
            self.batch,
            self.semester,
            self.bio,
            self.linkedin_url or self.github_url,
            self.skills.count() > 0,
            self.projects.count() > 0,
            self.certifications.count() > 0,
            self.resumes.count() > 0,
        ]
        return all(checks)


class StudentSkill(BaseModel):
    __tablename__ = "student_skills"
    __table_args__ = (
        db.UniqueConstraint("student_id", "skill_id", name="uq_student_skills"),
        db.Index("idx_student_skills_student_id", "student_id"),
        db.Index("idx_student_skills_skill_id", "skill_id"),
    )

    student_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    skill_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("skills.id", ondelete="RESTRICT"),
        nullable=False,
    )
    proficiency = db.Column(db.SmallInteger, nullable=False, default=3)
    years_experience = db.Column(db.Numeric(3, 1))

    def __repr__(self):
        return f"<StudentSkill student={self.student_id} skill={self.skill_id}>"


class StudentProject(BaseModel):
    __tablename__ = "student_projects"
    __table_args__ = (db.Index("idx_student_projects_student_id", "student_id"),)

    student_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    tech_stack = db.Column(db.Text)
    project_url = db.Column(db.String(500))
    repository_url = db.Column(db.String(500))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    is_ongoing = db.Column(db.Boolean, nullable=False, default=False)

    def __repr__(self):
        return f"<StudentProject {self.title}>"


class StudentCertification(BaseModel):
    __tablename__ = "student_certifications"
    __table_args__ = (db.Index("idx_student_certifications_student_id", "student_id"),)

    student_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = db.Column(db.String(255), nullable=False)
    issuer = db.Column(db.String(255), nullable=False)
    credential_id = db.Column(db.String(100))
    credential_url = db.Column(db.String(500))
    issue_date = db.Column(db.Date, nullable=False)
    expiry_date = db.Column(db.Date)

    def __repr__(self):
        return f"<StudentCertification {self.name}>"


class Resume(BaseModel):
    __tablename__ = "resumes"
    __table_args__ = (
        db.Index("idx_resumes_student_id", "student_id"),
        db.Index("idx_resumes_parse_status", "parse_status"),
        db.Index(
            "uq_resumes_primary_per_student",
            "student_id",
            unique=True,
            postgresql_where=text("is_primary = TRUE"),
        ),
    )

    student_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(1000), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    file_size_bytes = db.Column(db.BigInteger, nullable=False)
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    parsed_text = deferred(db.Column(db.Text))
    parse_status = db.Column(
        db.Enum(ParseStatus, name="parse_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ParseStatus.PENDING,
    )
    parsed_at = db.Column(db.DateTime(timezone=True))
    uploaded_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
    )

    applications = db.relationship(
        "Application",
        backref="resume",
        passive_deletes=True,
        lazy="dynamic",
    )

    def to_dict(self, exclude=None, include=None, exclude_relationships=True):
        default_exclude = {"parsed_text", "file_path"}
        exclude = set(exclude or []) | default_exclude
        return super().to_dict(
            exclude=exclude,
            include=include,
            exclude_relationships=exclude_relationships,
        )

    def __repr__(self):
        return f"<Resume {self.file_name}>"


class ProfileChangeRequest(BaseModel):
    __tablename__ = "profile_change_requests"
    __table_args__ = (
        db.Index("idx_profile_change_requests_student_id", "student_id"),
        db.Index("idx_profile_change_requests_status", "status"),
    )

    student_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_name = db.Column(db.String(100), nullable=False)
    old_value = db.Column(db.Text)
    requested_value = db.Column(db.Text, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending, approved, rejected
    reviewed_by = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="SET NULL"),
    )
    reviewed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
    )
    rejection_reason = db.Column(db.Text)

    student = db.relationship(
        "Student",
        backref=db.backref("change_requests", lazy="dynamic", cascade="all, delete-orphan"),
    )
    reviewer = db.relationship("User", backref="reviewed_change_requests")
